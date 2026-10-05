package org.dromara.gz.jp.job;

import org.dromara.DromaraApplication;
import org.dromara.common.tenant.helper.TenantHelper;
import org.dromara.gz.common.pay.domain.bo.GzPayTestCreateBo;
import org.dromara.gz.common.pay.domain.entity.GzPayTransaction;
import org.dromara.gz.common.pay.mapper.GzPayTransactionMapper;
import org.dromara.gz.common.pay.service.IGzPayTransactionService;
import org.dromara.gz.common.pay.service.IGzPayTransactionService.ReconcileOutcome;
import org.dromara.gz.common.pay.service.IPayOrderQueryService;
import org.dromara.gz.common.pay.service.internal.IWechatPayClient.NotifyContext;
import org.dromara.gz.common.pay.service.internal.MockWechatPayClient;
import org.dromara.gz.jp.domain.bo.GzJpMarkFailedBo;
import org.dromara.gz.jp.domain.bo.GzJpOrderSubmitBo;
import org.dromara.gz.jp.domain.vo.GzJpOrderSubmitVO;
import org.dromara.gz.jp.service.IGzJpCartService;
import org.dromara.gz.jp.service.IGzJpOrderService;
import org.dromara.gz.jp.service.IGzJpRefundService;
import org.dromara.gz.jp.mapper.GzJpOrderMapper;
import org.dromara.gz.jp.mapper.GzJpRefundMapper;
import org.dromara.gz.jp.domain.entity.GzJpOrder;
import org.dromara.gz.jp.domain.entity.GzJpRefund;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import javax.sql.DataSource;
import java.io.FileWriter;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * D7 QA r2 独立探针（QA 资产，非实现方）：针对返工改动的调用方补探针。
 * <ul>
 *   <li>applyPaid 被回调与查单补单（reconcilePaid）共用：返工把 affected=0 重读改成 FOR UPDATE 当前读，
 *       验两条路径真并发（各自先持锁、3 轮）下只落一次 processed、业务只推进一次、无死锁。</li>
 *   <li>兜底查单非空转：一张只被 markTimeout、从未收到回调的单，查单任务 SUCCESS → late_paid。</li>
 *   <li>markAcceptFailed 改为按守卫结果写商品行：非竞态下（发起 / admin 重试受理失败）行仍必须落 refund_failed。</li>
 * </ul>
 * 每个方法单独跑（scanAndReconcile 进程内 10 分钟节流）。
 */
@Tag("dev")
@SpringBootTest(classes = DromaraApplication.class)
class D7R2QaProbeTest {

    static final String SEED_FILE = System.getProperty("qa.seedFile",
        "/private/tmp/claude-501/-Users-wkui-Project-profile-project-freelance-projects-sensenran-guzi/29c58620-8228-4c77-bee8-fa98f8afa5e2/scratchpad/r2/seeded.txt");
    static final Long USER = 14L;
    static final Long PRODUCT = 904L;
    static final Long ADDRESS = 1L;
    static final long PRICE = 8000L;

    @Autowired IGzPayTransactionService payTxService;
    @Autowired GzPayTransactionMapper payTxMapper;
    @Autowired IPayOrderQueryService queryService;
    @Autowired MockWechatPayClient mock;
    @Autowired DataSource dataSource;
    @Autowired PlatformTransactionManager tm;
    @Autowired IGzJpCartService cartService;
    @Autowired IGzJpOrderService orderService;
    @Autowired IGzJpRefundService refundService;
    @Autowired GzJpOrderMapper jpOrderMapper;
    @Autowired GzJpRefundMapper jpRefundMapper;

    JdbcTemplate jdbc;
    final ExecutorService pool = Executors.newFixedThreadPool(4);

    @BeforeEach
    void init() {
        jdbc = new JdbcTemplate(dataSource);
    }

    @AfterEach
    void tearDown() {
        pool.shutdownNow();
        mock.setQueryTradeState("NOTPAY");
        mock.setRefundAcceptFail(false);
    }

    static synchronized void track(String kind, Object v) {
        try (FileWriter w = new FileWriter(SEED_FILE, true)) {
            w.write(kind + " " + v + "\n");
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    static void await(CountDownLatch l) {
        try {
            assertTrue(l.await(15, TimeUnit.SECONDS), "latch timeout");
        } catch (InterruptedException e) {
            throw new IllegalStateException(e);
        }
    }

    int waitLockWaits(int expected) {
        int n = 0;
        for (int i = 0; i < 100; i++) {
            n = jdbc.queryForObject("SELECT COUNT(*) FROM performance_schema.data_lock_waits", Integer.class);
            if (n >= expected) {
                return n;
            }
            try { Thread.sleep(50); } catch (InterruptedException e) { throw new IllegalStateException(e); }
        }
        return n;
    }

    Map<String, Integer> logCounts(String otn) {
        Map<String, Integer> m = new TreeMap<>();
        jdbc.queryForList("SELECT process_status s, COUNT(*) n FROM gz_pay_callback_log WHERE out_trade_no=? GROUP BY process_status", otn)
            .forEach(r -> m.put((String) r.get("s"), ((Number) r.get("n")).intValue()));
        return m;
    }

    record Seed(Long orderId, String otn, Long payId) {}

    Seed seedJpOrder() {
        GzJpOrderSubmitVO vo = TenantHelper.dynamic("1001", () -> {
            cartService.addItem(USER, PRODUCT, 1);
            Long cartId = jdbc.queryForObject("SELECT id FROM gz_jp_cart_item WHERE user_id=? AND product_id=? AND del_flag='0' ORDER BY id DESC LIMIT 1",
                Long.class, USER, PRODUCT);
            GzJpOrderSubmitBo bo = new GzJpOrderSubmitBo();
            bo.setCartItemIds(List.of(cartId));
            bo.setAddressId(ADDRESS);
            bo.setExpectedAmountCent(PRICE);
            return orderService.submit(bo, USER);
        });
        String otn = vo.getPayParams().getOutTradeNo();
        track("jporder", vo.getOrderId());
        track("pay", otn);
        Long payId = jdbc.queryForObject("SELECT id FROM gz_pay_transaction WHERE out_trade_no=?", Long.class, otn);
        return new Seed(vo.getOrderId(), otn, payId);
    }

    NotifyContext payCtx(String otn) {
        return new NotifyContext("0", "r2", "r2", "r2", mock.buildMockCallbackBody(otn, "mock_wx_txn_" + otn, PRICE));
    }

    // ---------------- applyPaid 两个调用方真并发 ----------------

    @Test
    @DisplayName("R2-P1 回调 vs 查单补单：一方持锁未提交、另一方卡在锁上，放行后只 processed 一次、订单 paid 一次（3 轮，交替先后）")
    void callbackVsReconcile() throws Exception {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 6; r++) {
            Seed s = seedJpOrder();
            boolean callbackFirst = r % 2 == 1;
            CountDownLatch inside = new CountDownLatch(1);
            CountDownLatch go = new CountDownLatch(1);
            Callable<Object> cb = () -> TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(s.otn())));
            Callable<Object> rc = () -> TenantHelper.ignore(() -> payTxService.reconcilePaid(s.payId(), "mock_wx_txn_" + s.otn(), null, "{\"qa\":\"r2\"}"));
            Callable<Object> first = callbackFirst ? cb : rc;
            Callable<Object> second = callbackFirst ? rc : cb;
            // 先手：包一层外部事务，跑完产品方法后不提交（持有 markPaid 的 X 锁）= 注入延迟
            Future<Object> f1 = pool.submit(() -> new TransactionTemplate(tm).execute(st -> {
                Object o;
                try {
                    o = first.call();
                } catch (Exception e) {
                    throw new IllegalStateException(e);
                }
                inside.countDown();
                await(go);
                return o;
            }));
            await(inside);
            Future<Object> f2 = pool.submit(second);
            int waits = waitLockWaits(1);
            go.countDown();
            Object o1 = f1.get(20, TimeUnit.SECONDS);
            Object o2 = f2.get(20, TimeUnit.SECONDS);
            String pay = jdbc.queryForObject("SELECT status FROM gz_pay_transaction WHERE id=?", String.class, s.payId());
            String order = jdbc.queryForObject("SELECT business_status FROM gz_jp_order WHERE id=?", String.class, s.orderId());
            Map<String, Integer> logs = logCounts(s.otn());
            System.out.println("[R2-P1] round=" + r + " first=" + (callbackFirst ? "callback" : "reconcile") + " otn=" + s.otn()
                + " lockWaits=" + waits + " out1=" + o1 + " out2=" + o2 + " pay=" + pay + " order=" + order + " logs=" + logs);
            if (waits < 1 || !"paid".equals(pay) || !"paid".equals(order) || logs.getOrDefault("processed", 0) != 1
                || logs.getOrDefault("late_paid", 0) != 0) {
                fails.add("round " + r + " otn=" + s.otn() + " pay=" + pay + " order=" + order + " logs=" + logs);
            }
        }
        assertTrue(fails.isEmpty(), "回调 / 查单并发推进异常：" + fails);
    }

    // ---------------- 兜底查单非空转 ----------------

    @Test
    @DisplayName("R2-P2 兜底查单：只被 markTimeout、从未收到回调的单 → 查单 SUCCESS 记 late_paid，状态仍 timeout")
    void backstopNonVacuous() {
        GzPayTestCreateBo bo = new GzPayTestCreateBo();
        bo.setAmountCent(1L);
        String otn = TenantHelper.dynamic("1001", () -> payTxService.createTestOrder(bo, 1L)).getOutTradeNo();
        track("pay", otn);
        GzPayTransaction t = TenantHelper.ignore(() -> payTxMapper.selectByOutTradeNo(otn));
        assertEquals(1, (int) TenantHelper.ignore(() -> payTxMapper.markTimeout(t.getId(), LocalDateTime.now())));
        Integer foreignPending = jdbc.queryForObject("SELECT COUNT(*) FROM gz_pay_transaction WHERE status='pending' AND del_flag='0' "
            + "AND create_time >= NOW() - INTERVAL 24 HOUR AND create_time <= NOW() - INTERVAL 5 MINUTE", Integer.class);
        List<String> foreignTimeoutNoLog = jdbc.queryForList("SELECT t.out_trade_no FROM gz_pay_transaction t WHERE t.status='timeout' AND t.del_flag='0' "
            + "AND t.closed_time >= NOW() - INTERVAL 24 HOUR AND t.out_trade_no<>? AND NOT EXISTS (SELECT 1 FROM gz_pay_callback_log l "
            + "WHERE l.out_trade_no=t.out_trade_no AND l.process_status='late_paid')", String.class, otn);
        System.out.println("[R2-P2] otn=" + otn + " before logs=" + logCounts(otn) + " foreignPending=" + foreignPending
            + " foreignTimeoutWithoutLatePaid=" + foreignTimeoutNoLog);
        Assumptions.assumeTrue(foreignPending == 0 && foreignTimeoutNoLog.isEmpty(), "窗口里有非本探针的单，跳过以免 mock SUCCESS 波及");
        assertEquals(0, logCounts(otn).getOrDefault("late_paid", 0));
        mock.setQueryTradeState("SUCCESS");
        try {
            System.out.println("[R2-P2] scan=" + queryService.scanAndReconcile());
        } finally {
            mock.setQueryTradeState("NOTPAY");
        }
        Map<String, Integer> logs = logCounts(otn);
        String st = jdbc.queryForObject("SELECT status FROM gz_pay_transaction WHERE out_trade_no=?", String.class, otn);
        Object paidTime = jdbc.queryForObject("SELECT paid_time FROM gz_pay_transaction WHERE out_trade_no=?", Object.class, otn);
        System.out.println("[R2-P2] otn=" + otn + " after status=" + st + " paid_time=" + paidTime + " logs=" + logs);
        assertEquals("timeout", st);
        assertNull(paidTime);
        assertEquals(1, logs.getOrDefault("late_paid", 0));
        assertEquals(0, logs.getOrDefault("processed", 0));
    }

    // ---------------- markAcceptFailed 非竞态行为不变 ----------------

    @Test
    @DisplayName("R2-P3 非竞态：发起退款受理失败 → 退款单与商品行都 refund_failed；admin 重试仍失败 → 同样落 refund_failed（3 轮）")
    void acceptFailedNoRaceStillWritesItem() {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            Seed s = seedJpOrder();
            assertTrue(TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(s.otn()))));
            Long itemId = jdbc.queryForObject("SELECT id FROM gz_jp_order_item WHERE order_id=? LIMIT 1", Long.class, s.orderId());
            GzJpMarkFailedBo bo = new GzJpMarkFailedBo();
            bo.setItemIds(List.of(itemId));
            bo.setReason("D7 r2 accept fail");
            mock.setRefundAcceptFail(true);
            Object res = TenantHelper.dynamic("1001", () -> refundService.markPurchaseFailedAndRefund(bo, 1L, "qa-d7-r2"));
            Long refundId = jdbc.queryForObject("SELECT id FROM gz_jp_refund WHERE order_item_id=?", Long.class, itemId);
            track("refund", refundId);
            Map<String, Object> rf1 = jdbc.queryForMap("SELECT status, attempt_count, fail_reason IS NOT NULL has_reason FROM gz_jp_refund WHERE id=?", refundId);
            String item1 = jdbc.queryForObject("SELECT refund_status FROM gz_jp_order_item WHERE id=?", String.class, itemId);
            String retryOut;
            try {
                TenantHelper.dynamic("1001", () -> refundService.retry(refundId, "qa-d7-r2"));
                retryOut = "ok";
            } catch (Exception e) {
                retryOut = "threw:" + e.getMessage();
            }
            mock.setRefundAcceptFail(false);
            Map<String, Object> rf2 = jdbc.queryForMap("SELECT status, attempt_count FROM gz_jp_refund WHERE id=?", refundId);
            String item2 = jdbc.queryForObject("SELECT refund_status FROM gz_jp_order_item WHERE id=?", String.class, itemId);
            System.out.println("[R2-P3] round=" + r + " otn=" + s.otn() + " apply=" + res + " afterApply refund=" + rf1 + " item=" + item1
                + " retry=" + retryOut + " afterRetry refund=" + rf2 + " item=" + item2);
            if (!"refund_failed".equals(rf1.get("status")) || !"refund_failed".equals(item1)
                || !"refund_failed".equals(rf2.get("status")) || !"refund_failed".equals(item2) || "ok".equals(retryOut)) {
                fails.add("round " + r + " refund=" + rf1 + "/" + rf2 + " item=" + item1 + "/" + item2 + " retry=" + retryOut);
            }
        }
        assertTrue(fails.isEmpty(), "受理失败未落 refund_failed：" + fails);
    }
    // ---------------- L3 时间边界（产品 mapper 的扫描口径） ----------------

    @Test
    @DisplayName("R2-L3 边界：迟到核查 24h 窗口（23h 纳入 / 25h 排除）、JP-110 15 分钟阈值（16 纳入 / 14 排除）、JP-111 10 分钟静默（11 纳入 / 9 排除）")
    void l3TimeBoundaries() {
        LocalDateTime now = LocalDateTime.now();
        // 迟到付款核查窗口
        GzPayTestCreateBo bo = new GzPayTestCreateBo();
        bo.setAmountCent(1L);
        String in23 = TenantHelper.dynamic("1001", () -> payTxService.createTestOrder(bo, 1L)).getOutTradeNo();
        String out25 = TenantHelper.dynamic("1001", () -> payTxService.createTestOrder(bo, 1L)).getOutTradeNo();
        track("pay", in23);
        track("pay", out25);
        jdbc.update("UPDATE gz_pay_transaction SET status='timeout', closed_time=NOW() - INTERVAL 23 HOUR WHERE out_trade_no=?", in23);
        jdbc.update("UPDATE gz_pay_transaction SET status='timeout', closed_time=NOW() - INTERVAL 25 HOUR WHERE out_trade_no=?", out25);
        Long id23 = jdbc.queryForObject("SELECT id FROM gz_pay_transaction WHERE out_trade_no=?", Long.class, in23);
        Long id25 = jdbc.queryForObject("SELECT id FROM gz_pay_transaction WHERE out_trade_no=?", Long.class, out25);
        List<Long> late = TenantHelper.ignore(() -> payTxMapper.selectLatePaidCheckTimeoutIds(now.minusHours(24), 500));
        System.out.println("[R2-L3] latePaidWindow ids23=" + id23 + " in=" + late.contains(id23) + " ids25=" + id25 + " in=" + late.contains(id25));
        assertTrue(late.contains(id23));
        assertFalse(late.contains(id25));
        // JP-110 阈值
        Seed a = seedJpOrder();
        Seed b = seedJpOrder();
        jdbc.update("UPDATE gz_jp_order SET create_time = NOW() - INTERVAL 16 MINUTE WHERE id=?", a.orderId());
        jdbc.update("UPDATE gz_jp_order SET create_time = NOW() - INTERVAL 14 MINUTE WHERE id=?", b.orderId());
        List<Long> exp = TenantHelper.ignore(() -> jpOrderMapper.selectUnpaidExpired(now.minusMinutes(15), 500)).stream().map(GzJpOrder::getId).toList();
        System.out.println("[R2-L3] unpaidExpire 16min=" + exp.contains(a.orderId()) + " 14min=" + exp.contains(b.orderId()));
        assertTrue(exp.contains(a.orderId()));
        assertFalse(exp.contains(b.orderId()));
        // JP-111 静默期（用两笔已付款单发起购买失败退款）
        List<Long> rids = new ArrayList<>();
        for (Seed s : List.of(a, b)) {
            assertTrue(TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(s.otn()))));
            Long itemId = jdbc.queryForObject("SELECT id FROM gz_jp_order_item WHERE order_id=? LIMIT 1", Long.class, s.orderId());
            GzJpMarkFailedBo mf = new GzJpMarkFailedBo();
            mf.setItemIds(List.of(itemId));
            mf.setReason("D7 r2 L3");
            TenantHelper.dynamic("1001", () -> refundService.markPurchaseFailedAndRefund(mf, 1L, "qa-d7-r2"));
            Long rid = jdbc.queryForObject("SELECT id FROM gz_jp_refund WHERE order_item_id=?", Long.class, itemId);
            track("refund", rid);
            rids.add(rid);
        }
        jdbc.update("UPDATE gz_jp_refund SET update_time = NOW() - INTERVAL 11 MINUTE WHERE id=?", rids.get(0));
        jdbc.update("UPDATE gz_jp_refund SET update_time = NOW() - INTERVAL 9 MINUTE WHERE id=?", rids.get(1));
        List<Long> stale = TenantHelper.ignore(() -> jpRefundMapper.selectStaleRefunding(LocalDateTime.now().minusMinutes(10), 500)).stream().map(GzJpRefund::getId).toList();
        System.out.println("[R2-L3] staleRefund 11min=" + stale.contains(rids.get(0)) + " 9min=" + stale.contains(rids.get(1)));
        assertTrue(stale.contains(rids.get(0)));
        assertFalse(stale.contains(rids.get(1)));
    }
}
