package org.dromara.gz.jp.job;

import org.dromara.DromaraApplication;
import org.dromara.common.tenant.helper.TenantHelper;
import org.dromara.gz.common.pay.service.IGzPayTransactionService;
import org.dromara.gz.common.pay.service.internal.IWechatPayClient.NotifyContext;
import org.dromara.gz.common.pay.service.internal.MockWechatPayClient;
import org.dromara.gz.jp.domain.bo.GzJpMarkFailedBo;
import org.dromara.gz.jp.domain.bo.GzJpOrderSubmitBo;
import org.dromara.gz.jp.domain.entity.GzJpRefund;
import org.dromara.gz.jp.domain.vo.GzJpOrderSubmitVO;
import org.dromara.gz.jp.mapper.GzJpRefundMapper;
import org.dromara.gz.jp.service.IGzJpCartService;
import org.dromara.gz.jp.service.IGzJpOrderService;
import org.dromara.gz.jp.service.IGzJpRefundService;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import javax.sql.DataSource;
import java.io.FileWriter;
import java.util.*;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * D7 QA r1 O2 回归（真库、独立连接、3 轮、注入延迟）：补发 / 重试「受理失败回写」与退款成功回调夹击。
 *
 * <p>形态：连接 1 = 退款 SUCCESS 回调（产品 handleRefundNotify，外包一层事务把提交推迟 = 注入延迟，
 * 期间已持退款单 / 商品行 X 锁）；连接 2 = 补偿补发（compensateStaleRefund NOT_FOUND → 微信受理抛错）
 * 或 admin 重新发起（retry，stale refunding → 微信受理抛错）→ markAcceptFailed → markFailed 卡在行锁上
 * （data_lock_waits ≥ 1）→ 放行连接 1 提交 → markFailed affected=0。</p>
 *
 * <p>不变量：钱已退成功的单，退款单 = refunded、商品行 refund_status = refunded 且 refund_amount_cent = 行金额、
 * 订单 rollup = refunded。修复前商品行被无条件改回 refund_failed（与退款单 refunded 不一致）。</p>
 */
@Tag("dev")
@SpringBootTest(classes = DromaraApplication.class)
class D7ReworkO2RefundRaceTest {

    static final String SEED_FILE = System.getProperty("qa.seedFile",
        "/private/tmp/claude-501/-Users-wkui-Project-profile-project-freelance-projects-sensenran-guzi/29c58620-8228-4c77-bee8-fa98f8afa5e2/scratchpad/rework/o2-seeded.txt");
    static final Long USER = 14L;
    static final Long PRODUCT = 904L;
    static final Long ADDRESS = 1L;
    static final long PRICE = 8000L;

    @Autowired IGzPayTransactionService payTxService;
    @Autowired MockWechatPayClient mock;
    @Autowired DataSource dataSource;
    @Autowired PlatformTransactionManager tm;
    @Autowired IGzJpCartService cartService;
    @Autowired IGzJpOrderService orderService;
    @Autowired IGzJpRefundService refundService;
    @Autowired GzJpRefundMapper refundMapper;

    JdbcTemplate jdbc;
    final ExecutorService pool = Executors.newFixedThreadPool(4);

    @BeforeEach
    void init() {
        jdbc = new JdbcTemplate(dataSource);
    }

    @AfterEach
    void tearDown() {
        pool.shutdownNow();
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

    GzJpRefund seedRefunding() {
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
        track("jporder", vo.getOrderId());
        String otn = vo.getPayParams().getOutTradeNo();
        track("pay", otn);
        assertTrue(TenantHelper.ignore(() -> payTxService.handlePaymentNotify(new NotifyContext("0", "o2", "o2", "o2",
            mock.buildMockCallbackBody(otn, "mock_wx_txn_" + otn, PRICE)))));
        Long itemId = jdbc.queryForObject("SELECT id FROM gz_jp_order_item WHERE order_id=? LIMIT 1", Long.class, vo.getOrderId());
        GzJpMarkFailedBo bo = new GzJpMarkFailedBo();
        bo.setItemIds(List.of(itemId));
        bo.setReason("D7 rework O2");
        TenantHelper.dynamic("1001", () -> refundService.markPurchaseFailedAndRefund(bo, 1L, "d7-rework"));
        Long refundId = jdbc.queryForObject("SELECT id FROM gz_jp_refund WHERE order_item_id=?", Long.class, itemId);
        track("refund", refundId);
        // 造「卡单」：静默期之外（补偿扫描与 admin 重试的放行口径）
        jdbc.update("UPDATE gz_jp_refund SET update_time = NOW() - INTERVAL 20 MINUTE, triggered_time = NOW() - INTERVAL 20 MINUTE WHERE id=?", refundId);
        GzJpRefund rf = TenantHelper.ignore(() -> refundMapper.selectById(refundId));
        assertEquals("refunding", rf.getStatus());
        return rf;
    }

    /** 跑一轮：连接 1 回调持锁未提交，连接 2 跑 failingSide，卡锁后放行。返回失败描述，null = 通过。 */
    String oneRound(String tag, int round, GzJpRefund rf, Callable<Object> failingSide) throws Exception {
        mock.setQueryRefundStatus(rf.getRefundNo(), null);
        CountDownLatch applied = new CountDownLatch(1);
        CountDownLatch go = new CountDownLatch(1);
        Future<Boolean> cb = pool.submit(() -> new TransactionTemplate(tm).execute(s -> {
            boolean ok = TenantHelper.ignore(() -> refundService.handleRefundNotify(new NotifyContext("0", "n", "s", "x",
                mock.buildMockRefundCallbackBody(rf.getOutTradeNo(), rf.getRefundNo(), "mock_refund_id_" + rf.getRefundNo(), "SUCCESS"))));
            applied.countDown();
            await(go);
            return ok;
        }));
        await(applied);
        mock.setRefundAcceptFail(true);
        Future<Object> side = pool.submit(() -> {
            try {
                return failingSide.call();
            } catch (Exception e) {
                return "threw:" + e.getMessage();
            }
        });
        int waits = waitLockWaits(1);
        go.countDown();
        boolean cbOk = cb.get(20, TimeUnit.SECONDS);
        Object sideOut = side.get(20, TimeUnit.SECONDS);
        mock.setRefundAcceptFail(false);
        Map<String, Object> refund = jdbc.queryForMap("SELECT status, fail_reason FROM gz_jp_refund WHERE id=?", rf.getId());
        Map<String, Object> item = jdbc.queryForMap("SELECT refund_status, refund_amount_cent, amount_cent FROM gz_jp_order_item WHERE id=?", rf.getOrderItemId());
        String os = jdbc.queryForObject("SELECT business_status FROM gz_jp_order WHERE id=?", String.class, rf.getOrderId());
        System.out.println("[O2-" + tag + "] round=" + round + " refund_no=" + rf.getRefundNo() + " lockWaitsSeen=" + waits
            + " cbOk=" + cbOk + " side=" + sideOut + " refund=" + refund + " item=" + item + " order=" + os);
        Number amt = (Number) item.get("refund_amount_cent");
        if (waits < 1 || !"refunded".equals(refund.get("status")) || !"refunded".equals(item.get("refund_status"))
            || amt == null || amt.longValue() != rf.getRefundAmountCent() || !"refunded".equals(os)) {
            return "round " + round + " refund_no=" + rf.getRefundNo() + " waits=" + waits + " refund=" + refund + " item=" + item + " order=" + os;
        }
        return null;
    }

    @Test
    @DisplayName("O2 补偿补发失败 vs 退款成功回调：回调先落账 → 商品行不得被改回 refund_failed（3 轮）")
    void compensateResendFailed_vsRefundCallback() throws Exception {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            GzJpRefund rf = seedRefunding();
            String f = oneRound("COMPENSATE", r, rf, () -> TenantHelper.ignore(() -> refundService.compensateStaleRefund(rf)));
            if (f != null) {
                fails.add(f);
            }
        }
        assertTrue(fails.isEmpty(), "已退款成功的商品行被改回 refund_failed：" + fails);
    }

    @Test
    @DisplayName("O2 admin 重新发起失败 vs 退款成功回调：回调先落账 → 商品行不得被改回 refund_failed（3 轮）")
    void retryFailed_vsRefundCallback() throws Exception {
        List<String> fails = new ArrayList<>();
        for (int r = 1; r <= 3; r++) {
            GzJpRefund rf = seedRefunding();
            String f = oneRound("RETRY", r, rf, () -> TenantHelper.dynamic("1001", () -> refundService.retry(rf.getId(), "d7-rework")));
            if (f != null) {
                fails.add(f);
            }
        }
        assertTrue(fails.isEmpty(), "已退款成功的商品行被改回 refund_failed：" + fails);
    }
}
