package org.dromara.gz.jp.job;

import org.dromara.DromaraApplication;
import org.dromara.common.tenant.helper.TenantHelper;
import org.dromara.gz.common.pay.domain.bo.GzPayTestCreateBo;
import org.dromara.gz.common.pay.domain.entity.GzPayTransaction;
import org.dromara.gz.common.pay.mapper.GzPayTransactionMapper;
import org.dromara.gz.common.pay.service.IGzPayTransactionService;
import org.dromara.gz.common.pay.service.IPayOrderQueryService;
import org.dromara.gz.common.pay.service.internal.IWechatPayClient;
import org.dromara.gz.common.pay.service.internal.IWechatPayClient.NotifyContext;
import org.dromara.gz.common.pay.service.internal.MockWechatPayClient;
import org.dromara.gz.jp.domain.bo.GzJpMarkFailedBo;
import org.dromara.gz.jp.domain.bo.GzJpOrderSubmitBo;
import org.dromara.gz.jp.domain.entity.GzJpOrder;
import org.dromara.gz.jp.domain.entity.GzJpRefund;
import org.dromara.gz.jp.domain.vo.GzJpOrderSubmitVO;
import org.dromara.gz.jp.mapper.GzJpOrderMapper;
import org.dromara.gz.jp.mapper.GzJpRefundMapper;
import org.dromara.gz.jp.service.IGzJpCartService;
import org.dromara.gz.jp.service.IGzJpOrderService;
import org.dromara.gz.jp.service.IGzJpRefundService;
import org.dromara.gz.jp.service.IGzJpRefundService.CompensateOutcome;
import org.dromara.gz.jp.service.internal.GzJpUnpaidExpireTxService;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import javax.sql.DataSource;
import java.io.FileWriter;
import java.lang.reflect.Proxy;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * D7 QA（独立 QA 资产，非实现方）：真库并发形态 —— PAY-106 回调 vs 超时 / JP-110 关单 vs 支付回调 /
 * JP-111 补偿 vs 退款回调。≥2 独立连接、3 轮、临界区注入延迟（行锁持有 / 外部调用阻塞），断言打在 DB 不变量 +
 * 外部副作用次数上。数据全部走产品代码真 seed（购物车→下单→mock 通道支付），用完由 QA 精确硬删。
 */
@Tag("dev")
@SpringBootTest(classes = DromaraApplication.class)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class D7QaConcurrencyTest {

    static final String SEED_FILE = System.getProperty("qa.seedFile", "/private/tmp/claude-501/-Users-wkui-Project-profile-project-freelance-projects-sensenran-guzi/29c58620-8228-4c77-bee8-fa98f8afa5e2/scratchpad/qa-d7-seeded.txt");
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
    @Autowired GzJpRefundMapper refundMapper;
    @Autowired GzJpUnpaidExpireTxService jpTxService;

    JdbcTemplate jdbc;
    final ExecutorService pool = Executors.newFixedThreadPool(4);
    static final List<String> raceOtns = new ArrayList<>();

    @BeforeEach
    void init() {
        jdbc = new JdbcTemplate(dataSource);
    }

    @AfterEach
    void tearDown() {
        pool.shutdownNow();
        mock.setQueryTradeState("NOTPAY");
    }

    // ---------------- helpers ----------------

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

    String createTestPay() {
        GzPayTestCreateBo bo = new GzPayTestCreateBo();
        bo.setAmountCent(1L);
        String otn = TenantHelper.dynamic("1001", () -> payTxService.createTestOrder(bo, 1L)).getOutTradeNo();
        track("pay", otn);
        return otn;
    }

    GzPayTransaction tx(String otn) {
        return TenantHelper.ignore(() -> payTxMapper.selectByOutTradeNo(otn));
    }

    NotifyContext payCtx(String otn, long amount) {
        return new NotifyContext("0", "qa_nonce", "qa_sig", "qa_serial",
            mock.buildMockCallbackBody(otn, "mock_wx_txn_" + otn, amount));
    }

    Map<String, Integer> logCounts(String otn, long afterId) {
        Map<String, Integer> m = new TreeMap<>();
        jdbc.queryForList("SELECT process_status s, COUNT(*) n FROM gz_pay_callback_log WHERE out_trade_no=? AND id>? GROUP BY process_status",
            otn, afterId).forEach(r -> m.put((String) r.get("s"), ((Number) r.get("n")).intValue()));
        return m;
    }

    long maxLogId() {
        Long v = jdbc.queryForObject("SELECT COALESCE(MAX(id),0) FROM gz_pay_callback_log", Long.class);
        return v == null ? 0 : v;
    }

    record Seed(Long orderId, String orderNo, String otn) {}

    Seed seedJpOrder() {
        return TenantHelper.dynamic("1001", () -> {
            cartService.addItem(USER, PRODUCT, 1);
            Long cartId = jdbc.queryForObject("SELECT id FROM gz_jp_cart_item WHERE user_id=? AND product_id=? AND del_flag='0' ORDER BY id DESC LIMIT 1",
                Long.class, USER, PRODUCT);
            GzJpOrderSubmitBo bo = new GzJpOrderSubmitBo();
            bo.setCartItemIds(List.of(cartId));
            bo.setAddressId(ADDRESS);
            bo.setExpectedAmountCent(PRICE);
            GzJpOrderSubmitVO vo = orderService.submit(bo, USER);
            track("jporder", vo.getOrderId());
            track("pay", vo.getPayParams().getOutTradeNo());
            return new Seed(vo.getOrderId(), vo.getOrderNo(), vo.getPayParams().getOutTradeNo());
        });
    }

    String orderStatus(Long orderId) {
        return jdbc.queryForObject("SELECT business_status FROM gz_jp_order WHERE id=?", String.class, orderId);
    }

    // ---------------- PAY-106 ----------------

    @Test
    @Order(1)
    @DisplayName("PAY-106 L1 顺序：timeout 已提交 → 成功回调 → late_paid，不推进 paid（3 轮）")
    void pay106_sequential_timeoutThenCallback() {
        for (int r = 1; r <= 3; r++) {
            String otn = createTestPay();
            GzPayTransaction t = tx(otn);
            long before = maxLogId();
            int aff = TenantHelper.ignore(() -> payTxMapper.markTimeout(t.getId(), LocalDateTime.now()));
            assertEquals(1, aff);
            boolean ok = TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(otn, 1)));
            Map<String, Integer> logs = logCounts(otn, before);
            String st = tx(otn).getStatus();
            System.out.println("[QA-PAY106-SEQ] round=" + r + " otn=" + otn + " ok=" + ok + " status=" + st + " logs=" + logs);
            assertEquals("timeout", st);
            assertEquals(1, logs.getOrDefault("late_paid", 0));
            assertEquals(0, logs.getOrDefault("processed", 0));
            assertEquals(0, logs.getOrDefault("duplicated", 0));
        }
    }

    @Test
    @Order(2)
    @DisplayName("PAY-106 L1 并发：回调读到 pending 后、markPaid 前超时任务提交 timeout → 必须记 late_paid（3 轮）")
    void pay106_race_callbackVsTimeout() throws Exception {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            String otn = createTestPay();
            raceOtns.add(otn);
            Long id = tx(otn).getId();
            long before = maxLogId();
            CountDownLatch locked = new CountDownLatch(1);
            CountDownLatch go = new CountDownLatch(1);
            AtomicInteger timeoutAffected = new AtomicInteger(-1);
            // 连接 1：超时任务（产品 mapper.markTimeout），先持行锁 = 注入延迟，让回调卡在 markPaid 之前读完快照
            Future<?> holder = pool.submit(() -> TenantHelper.ignore(() -> new TransactionTemplate(tm).executeWithoutResult(s -> {
                payTxMapper.selectByIdForUpdate(id);
                locked.countDown();
                await(go);
                timeoutAffected.set(payTxMapper.markTimeout(id, LocalDateTime.now()));
            })));
            await(locked);
            // 连接 2：支付成功回调（产品 handlePaymentNotify，与 /simulate-callback、/api/pay/v3/notify 同链路）
            Future<Boolean> cb = pool.submit(() -> TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(otn, 1))));
            int waits = waitLockWaits(1);
            go.countDown();
            holder.get(20, TimeUnit.SECONDS);
            boolean ok = cb.get(20, TimeUnit.SECONDS);
            String st = tx(otn).getStatus();
            Map<String, Integer> logs = logCounts(otn, before);
            System.out.println("[QA-PAY106-RACE] round=" + r + " otn=" + otn + " lockWaitsSeen=" + waits
                + " timeoutAffected=" + timeoutAffected.get() + " cbOk=" + ok + " status=" + st + " logs=" + logs);
            if (!"timeout".equals(st) || logs.getOrDefault("late_paid", 0) < 1) {
                fails.add("round " + r + " otn=" + otn + " status=" + st + " logs=" + logs);
            }
        }
        assertTrue(fails.isEmpty(), "迟到付款在并发超时下被吞：" + fails);
    }

    @Test
    @Order(3)
    @DisplayName("PAY-106 兜底：查单任务对近 24h timeout 单查单 SUCCESS → late_paid（对并发轮的单）")
    void pay106_backstop_queryJob() {
        Integer foreignPending = jdbc.queryForObject("SELECT COUNT(*) FROM gz_pay_transaction WHERE status='pending' AND del_flag='0' "
            + "AND create_time >= NOW() - INTERVAL 24 HOUR AND create_time <= NOW() - INTERVAL 5 MINUTE", Integer.class);
        Integer foreignTimeout = jdbc.queryForObject("SELECT COUNT(*) FROM gz_pay_transaction WHERE status='timeout' AND del_flag='0' "
            + "AND closed_time >= NOW() - INTERVAL 24 HOUR", Integer.class);
        System.out.println("[QA-PAY106-BACKSTOP] pendingInQueryWindow=" + foreignPending + " timeout24h=" + foreignTimeout + " raceOtns=" + raceOtns);
        Assumptions.assumeTrue(foreignPending == 0, "查单窗口里有非 QA pending 单，跳过以免 mock SUCCESS 推进别人的单");
        mock.setQueryTradeState("SUCCESS");
        try {
            System.out.println("[QA-PAY106-BACKSTOP] scan=" + queryService.scanAndReconcile());
        } finally {
            mock.setQueryTradeState("NOTPAY");
        }
        for (String otn : raceOtns) {
            Map<String, Integer> logs = logCounts(otn, 0);
            String st = tx(otn).getStatus();
            System.out.println("[QA-PAY106-BACKSTOP] otn=" + otn + " status=" + st + " logs=" + logs);
            assertEquals("timeout", st);
            assertTrue(logs.getOrDefault("late_paid", 0) >= 1, "兜底查单也没记 late_paid: " + otn);
        }
    }

    // ---------------- JP-110 ----------------

    GzJpUnpaidExpireJob jobWith(IWechatPayClient client) {
        return new GzJpUnpaidExpireJob(jpOrderMapper, payTxMapper, client, payTxService, jpTxService, 15);
    }

    @Test
    @Order(10)
    @DisplayName("JP-110 L1 状态：NOTPAY → 先关微信单再关本地单；微信 SUCCESS → 补推进 paid 不关")
    void jp110_states() {
        mock.setQueryTradeState("NOTPAY");
        Seed a = seedJpOrder();
        jdbc.update("UPDATE gz_jp_order SET create_time = NOW() - INTERVAL 20 MINUTE WHERE id=?", a.orderId());
        int closeBefore = mock.getCloseOrderCallCount();
        GzJpOrder oa = TenantHelper.ignore(() -> jpOrderMapper.selectById(a.orderId()));
        GzJpUnpaidExpireJob.Outcome outA = TenantHelper.ignore(() -> jobWith(mock).expireOne(oa));
        String sa = orderStatus(a.orderId());
        Object ct = jdbc.queryForObject("SELECT cancelled_time FROM gz_jp_order WHERE id=?", Object.class, a.orderId());
        System.out.println("[QA-JP110-STATE] NOTPAY order=" + a.orderNo() + " outcome=" + outA + " status=" + sa
            + " cancelled_time=" + ct + " closeOrderCalls=" + (mock.getCloseOrderCallCount() - closeBefore));
        assertEquals(GzJpUnpaidExpireJob.Outcome.CANCELLED, outA);
        assertEquals("cancelled", sa);
        assertNotNull(ct);
        assertEquals(1, mock.getCloseOrderCallCount() - closeBefore);

        Seed b = seedJpOrder();
        jdbc.update("UPDATE gz_jp_order SET create_time = NOW() - INTERVAL 20 MINUTE WHERE id=?", b.orderId());
        mock.setQueryTradeState("SUCCESS");
        int closeBefore2 = mock.getCloseOrderCallCount();
        GzJpOrder ob = TenantHelper.ignore(() -> jpOrderMapper.selectById(b.orderId()));
        GzJpUnpaidExpireJob.Outcome outB = TenantHelper.ignore(() -> jobWith(mock).expireOne(ob));
        mock.setQueryTradeState("NOTPAY");
        String sb = orderStatus(b.orderId());
        System.out.println("[QA-JP110-STATE] SUCCESS order=" + b.orderNo() + " outcome=" + outB + " status=" + sb
            + " payStatus=" + tx(b.otn()).getStatus() + " closeOrderCalls=" + (mock.getCloseOrderCallCount() - closeBefore2));
        assertEquals(GzJpUnpaidExpireJob.Outcome.RECOVERED_PAID, outB);
        assertEquals("paid", sb);
        assertEquals("paid", tx(b.otn()).getStatus());
        assertEquals(0, mock.getCloseOrderCallCount() - closeBefore2);
    }

    @Test
    @Order(11)
    @DisplayName("JP-110 L1 并发：关单任务卡在关微信单时支付回调抢先 → 本地不能取消已付款单（3 轮）")
    void jp110_race_expireVsPayCallback() throws Exception {
        mock.setQueryTradeState("NOTPAY");
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            Seed s = seedJpOrder();
            jdbc.update("UPDATE gz_jp_order SET create_time = NOW() - INTERVAL 20 MINUTE WHERE id=?", s.orderId());
            long before = maxLogId();
            CountDownLatch inClose = new CountDownLatch(1);
            CountDownLatch go = new CountDownLatch(1);
            AtomicInteger closeCalls = new AtomicInteger();
            // 外部调用注入延迟：closeOrder 阻塞到回调完成
            IWechatPayClient slow = (IWechatPayClient) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class[]{IWechatPayClient.class}, (p, m, args) -> {
                    if ("closeOrder".equals(m.getName())) {
                        closeCalls.incrementAndGet();
                        inClose.countDown();
                        await(go);
                    }
                    try {
                        return m.invoke(mock, args);
                    } catch (java.lang.reflect.InvocationTargetException e) {
                        throw e.getCause();
                    }
                });
            GzJpOrder o = TenantHelper.ignore(() -> jpOrderMapper.selectById(s.orderId()));
            Future<GzJpUnpaidExpireJob.Outcome> job = pool.submit(() -> TenantHelper.ignore(() -> jobWith(slow).expireOne(o)));
            await(inClose);
            Future<Boolean> cb = pool.submit(() -> TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(s.otn(), PRICE))));
            boolean ok = cb.get(20, TimeUnit.SECONDS);
            go.countDown();
            GzJpUnpaidExpireJob.Outcome out = job.get(20, TimeUnit.SECONDS);
            String st = orderStatus(s.orderId());
            Object ct = jdbc.queryForObject("SELECT cancelled_time FROM gz_jp_order WHERE id=?", Object.class, s.orderId());
            Map<String, Integer> logs = logCounts(s.otn(), before);
            System.out.println("[QA-JP110-RACE] round=" + r + " order=" + s.orderNo() + " cbOk=" + ok + " jobOutcome=" + out
                + " orderStatus=" + st + " cancelled_time=" + ct + " payStatus=" + tx(s.otn()).getStatus()
                + " closeOrderCalls=" + closeCalls.get() + " logs=" + logs);
            if (!"paid".equals(st) || ct != null || out == GzJpUnpaidExpireJob.Outcome.CANCELLED
                || logs.getOrDefault("processed", 0) != 1 || closeCalls.get() != 1) {
                fails.add("round " + r + " order=" + s.orderNo() + " status=" + st + " outcome=" + out);
            }
        }
        assertTrue(fails.isEmpty(), "已付款单被关：" + fails);
    }

    // ---------------- JP-111 ----------------

    GzJpRefund seedRefunding() {
        Seed s = seedJpOrder();
        assertTrue(TenantHelper.ignore(() -> payTxService.handlePaymentNotify(payCtx(s.otn(), PRICE))));
        assertEquals("paid", orderStatus(s.orderId()));
        Long itemId = jdbc.queryForObject("SELECT id FROM gz_jp_order_item WHERE order_id=? LIMIT 1", Long.class, s.orderId());
        GzJpMarkFailedBo bo = new GzJpMarkFailedBo();
        bo.setItemIds(List.of(itemId));
        bo.setReason("QA D7 并发补偿");
        TenantHelper.dynamic("1001", () -> refundService.markPurchaseFailedAndRefund(bo, 1L, "qa-d7"));
        GzJpRefund rf = TenantHelper.ignore(() -> refundMapper.selectList(
            com.baomidou.mybatisplus.core.toolkit.Wrappers.<GzJpRefund>lambdaQuery().eq(GzJpRefund::getOrderItemId, itemId))).get(0);
        track("refund", rf.getId());
        assertEquals("refunding", rf.getStatus());
        jdbc.update("UPDATE gz_jp_refund SET update_time = NOW() - INTERVAL 20 MINUTE WHERE id=?", rf.getId());
        return TenantHelper.ignore(() -> refundMapper.selectById(rf.getId()));
    }

    @Test
    @Order(20)
    @DisplayName("JP-111 L1：微信侧无此退款单 → 同号补发、attempt+1、不新建退款单")
    void jp111_notFound_resendSameNo() {
        GzJpRefund rf = seedRefunding();
        mock.setQueryRefundStatus(rf.getRefundNo(), null);
        CompensateOutcome out = TenantHelper.ignore(() -> refundService.compensateStaleRefund(rf));
        Map<String, Object> row = jdbc.queryForMap("SELECT refund_no,status,attempt_count FROM gz_jp_refund WHERE id=?", rf.getId());
        Integer rows = jdbc.queryForObject("SELECT COUNT(*) FROM gz_jp_refund WHERE order_item_id=?", Integer.class, rf.getOrderItemId());
        System.out.println("[QA-JP111-NOTFOUND] refund=" + rf.getRefundNo() + " attemptBefore=" + rf.getAttemptCount()
            + " outcome=" + out + " after=" + row + " refundRowsForItem=" + rows);
        assertEquals(CompensateOutcome.RESENT, out);
        assertEquals(rf.getRefundNo(), row.get("refund_no"));
        assertEquals("refunding", row.get("status"));
        assertEquals((rf.getAttemptCount() == null ? 0 : rf.getAttemptCount()) + 1, ((Number) row.get("attempt_count")).intValue());
        assertEquals(1, rows);
    }

    @Test
    @Order(21)
    @DisplayName("JP-111 L1 并发：补偿查单 SUCCESS 与退款成功回调同时落账 → 只落一次（3 轮，交替先后）")
    void jp111_race_compensateVsRefundCallback() throws Exception {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            GzJpRefund rf = seedRefunding();
            mock.setQueryRefundStatus(rf.getRefundNo(), "SUCCESS");
            long before = maxLogId();
            CountDownLatch locked = new CountDownLatch(1);
            CountDownLatch go = new CountDownLatch(1);
            Future<?> holder = pool.submit(() -> new TransactionTemplate(tm).executeWithoutResult(s -> {
                jdbc.queryForObject("SELECT id FROM gz_jp_refund WHERE id=? FOR UPDATE", Long.class, rf.getId());
                locked.countDown();
                await(go);
            }));
            await(locked);
            Callable<CompensateOutcome> comp = () -> TenantHelper.ignore(() -> refundService.compensateStaleRefund(rf));
            Callable<Boolean> cb = () -> TenantHelper.ignore(() -> refundService.handleRefundNotify(new NotifyContext("0", "n", "s", "x",
                mock.buildMockRefundCallbackBody(rf.getOutTradeNo(), rf.getRefundNo(), "mock_refund_id_" + rf.getRefundNo(), "SUCCESS"))));
            Future<CompensateOutcome> fComp;
            Future<Boolean> fCb;
            int w1;
            int w2;
            if (r % 2 == 1) {
                fCb = pool.submit(cb);
                w1 = waitLockWaits(1);
                fComp = pool.submit(comp);
                w2 = waitLockWaits(2);
            } else {
                fComp = pool.submit(comp);
                w1 = waitLockWaits(1);
                fCb = pool.submit(cb);
                w2 = waitLockWaits(2);
            }
            go.countDown();
            holder.get(20, TimeUnit.SECONDS);
            CompensateOutcome co = fComp.get(20, TimeUnit.SECONDS);
            boolean cbOk = fCb.get(20, TimeUnit.SECONDS);
            Map<String, Object> refund = jdbc.queryForMap("SELECT status, refunded_time, wechat_refund_id FROM gz_jp_refund WHERE id=?", rf.getId());
            Map<String, Object> item = jdbc.queryForMap("SELECT refund_status, refund_amount_cent, amount_cent FROM gz_jp_order_item WHERE id=?", rf.getOrderItemId());
            String os = orderStatus(rf.getOrderId());
            Map<String, Integer> logs = logCounts(rf.getOutTradeNo(), before);
            System.out.println("[QA-JP111-RACE] round=" + r + " first=" + (r % 2 == 1 ? "callback" : "compensate")
                + " lockWaits=" + w1 + "/" + w2 + " compOutcome=" + co + " cbOk=" + cbOk + " refund=" + refund
                + " item=" + item + " orderStatus=" + os + " logs=" + logs);
            boolean onceOk = logs.getOrDefault("processed", 0) == 1;
            if (!"refunded".equals(refund.get("status")) || !onceOk || !"refunded".equals(item.get("refund_status"))
                || ((Number) item.get("refund_amount_cent")).longValue() != rf.getRefundAmountCent()
                || !"refunded".equals(os)) {
                fails.add("round " + r + " refund=" + rf.getRefundNo() + " logs=" + logs + " order=" + os);
            }
        }
        assertTrue(fails.isEmpty(), "退款落账重复或不一致：" + fails);
    }
}
