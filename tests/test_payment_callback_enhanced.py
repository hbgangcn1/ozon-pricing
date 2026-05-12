# -*- coding: utf-8 -*-
"""
payment_callback_enhanced.py 单元测试
"""
import pytest
import time
from unittest.mock import MagicMock, patch


class TestPaymentCallbackEnhanced:
    """测试增强支付回调处理器"""

    @pytest.fixture
    def monitor(self):
        with patch("payment_callback_enhanced.logger"):
            from payment_callback_enhanced import PaymentCallbackEnhanced
            return PaymentCallbackEnhanced(
                queue_maxsize=100,
                queue_warning_threshold=80,
                queue_critical_threshold=90,
                max_retries=3,
                retry_interval=60,
                check_interval=60,
            )

    def test_init_default_values(self):
        with patch("payment_callback_enhanced.logger"):
            from payment_callback_enhanced import PaymentCallbackEnhanced
            m = PaymentCallbackEnhanced()
            assert m.queue_maxsize == 1000
            assert m.max_retries == 3
            assert m.retry_interval == 60
            assert m.monitoring is False

    def test_init_custom_values(self):
        with patch("payment_callback_enhanced.logger"):
            from payment_callback_enhanced import PaymentCallbackEnhanced
            m = PaymentCallbackEnhanced(
                queue_maxsize=500,
                queue_warning_threshold=400,
                queue_critical_threshold=450,
                max_retries=5,
                retry_interval=120,
                check_interval=30,
            )
            assert m.queue_maxsize == 500
            assert m.queue_warning_threshold == 400
            assert m.queue_critical_threshold == 450
            assert m.max_retries == 5
            assert m.retry_interval == 120
            assert m.check_interval == 30

    def test_get_retry_count_not_in_queue(self, monitor):
        assert monitor._get_retry_count("nonexistent") == 0

    def test_get_retry_count_in_queue(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            monitor.retry_queue.append(
                PaymentRetryRecord(
                    order_id="order1",
                    retry_count=2,
                    first_attempt_time=time.time(),
                    last_attempt_time=time.time(),
                    next_retry_time=time.time() + 60,
                )
            )
        assert monitor._get_retry_count("order1") == 2

    def test_enqueue_order_success(self, monitor):
        with patch.object(monitor, "process_order", return_value=True) as mock_process:
            result = monitor.enqueue_order("order1")
            assert result["success"] is True
            mock_process.assert_called_once_with("order1")

    def test_enqueue_order_failure_with_retry(self, monitor):
        with patch.object(monitor, "process_order", return_value=False):
            with patch.object(monitor, "_get_retry_count", return_value=1):
                result = monitor.enqueue_order("order1")
                assert result["success"] is True
                assert result["retry_count"] == 1

    def test_enqueue_order_failure_no_more_retries(self, monitor):
        with patch.object(monitor, "process_order", return_value=False):
            with patch.object(monitor, "_get_retry_count", return_value=0):
                with patch.object(monitor, "record_alert"):
                    with patch("payment_callback_enhanced.logger"):
                        result = monitor.enqueue_order("order1")
                        assert result["success"] is False

    def test_add_to_retry_queue_new_order(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            result = monitor._add_to_retry_queue("order1", 0, "test error")
            assert result["success"] is True
            assert result["retry_count"] == 1
            assert len(monitor.retry_queue) == 1

    def test_add_to_retry_queue_existing_order(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            monitor.retry_queue.append(
                PaymentRetryRecord(
                    order_id="order1",
                    retry_count=1,
                    first_attempt_time=time.time(),
                    last_attempt_time=time.time(),
                    next_retry_time=time.time(),
                )
            )
        with patch("payment_callback_enhanced.logger"):
            result = monitor._add_to_retry_queue("order1", 1, "test error")
            assert result["success"] is True
            assert result["retry_count"] == 2
            assert len(monitor.retry_queue) == 1
            assert monitor.retry_queue[0].retry_count == 2

    def test_add_to_retry_queue_full(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            for i in range(monitor.MAX_RETRY_QUEUE_SIZE):
                monitor.retry_queue.append(
                    PaymentRetryRecord(
                        order_id=f"order{i}",
                        retry_count=0,
                        first_attempt_time=time.time(),
                        last_attempt_time=time.time(),
                        next_retry_time=time.time(),
                    )
                )
        with patch("payment_callback_enhanced.logger"):
            result = monitor._add_to_retry_queue("order_overflow", 0, "error")
            assert result["success"] is False
            assert "重试队列已满" in result["message"]

    def test_process_order_success(self, monitor):
        with patch.object(monitor, "_run_payment_success_handler") as mock_handler:
            with patch("payment_callback_enhanced.logger"):
                result = monitor.process_order("order1")
                assert result is True
                mock_handler.assert_called_once_with("order1")
                assert monitor.stats["processed"] == 1
                assert monitor.stats["failed"] == 0

    def test_process_order_failure_with_retries(self, monitor):
        with patch.object(monitor, "_run_payment_success_handler", side_effect=Exception("error")):
            with patch.object(monitor, "_get_retry_count", return_value=0):
                with patch.object(monitor, "_add_to_retry_queue") as mock_add:
                    mock_add.return_value = {"success": True}
                    with patch("payment_callback_enhanced.logger"):
                        result = monitor.process_order("order1")
                        assert result is False
                        assert monitor.stats["failed"] == 1
                        mock_add.assert_called_once()

    def test_process_order_failure_retry_exhausted(self, monitor):
        with patch.object(monitor, "_run_payment_success_handler", side_effect=Exception("error")):
            with patch.object(monitor, "_get_retry_count", return_value=3):
                with patch.object(monitor, "record_alert") as mock_alert:
                    with patch("payment_callback_enhanced.logger"):
                        result = monitor.process_order("order1")
                        assert result is False
                        mock_alert.assert_called_once()
                        call_args = mock_alert.call_args
                        assert call_args[0][0] == "retry_exhausted"

    def test_reject_retry_queue_entry(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor, "record_alert") as mock_alert:
                result = monitor._reject_retry_queue_entry("order1", "test error")
                assert result["success"] is False
                assert "重试队列已满" in result["message"]
                assert monitor.stats["queue_full_count"] == 1
                mock_alert.assert_called_once()

    def test_add_to_retry_queue_backpressure(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord

        monitor.MAX_RETRY_QUEUE_SIZE = 1000
        with monitor.retry_lock:
            for i in range(901):
                monitor.retry_queue.append(
                    PaymentRetryRecord(
                        order_id=f"order{i}",
                        retry_count=0,
                        first_attempt_time=time.time(),
                        last_attempt_time=time.time(),
                        next_retry_time=time.time(),
                    )
                )
        with patch("payment_callback_enhanced.logger"):
            result = monitor._add_to_retry_queue("order_backpressure", 0, "error")
            assert result["success"] is False
            assert "重试队列已满" in result["message"]

    def test_process_retry_queue_empty(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            monitor.process_retry_queue()
            assert len(monitor.retry_queue) == 0

    def test_process_retry_queue_orders_ready(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            monitor.retry_queue.append(
                PaymentRetryRecord(
                    order_id="order1",
                    retry_count=0,
                    first_attempt_time=time.time() - 100,
                    last_attempt_time=time.time() - 100,
                    next_retry_time=time.time() - 1,
                    max_retries=3,
                )
            )
        with patch.object(monitor, "process_order", return_value=True) as mock_process:
            with patch("payment_callback_enhanced.logger"):
                monitor.process_retry_queue()
                mock_process.assert_called_once_with("order1")

    def test_check_queue_status_normal(self, monitor):
        with patch.object(monitor, "record_alert") as mock_alert:
            monitor.check_queue_status()
            mock_alert.assert_not_called()

    def test_check_queue_status_warning(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            for i in range(85):
                monitor.retry_queue.append(
                    PaymentRetryRecord(
                        order_id=f"order{i}",
                        retry_count=0,
                        first_attempt_time=time.time(),
                        last_attempt_time=time.time(),
                        next_retry_time=time.time() + 60,
                    )
                )
        with patch.object(monitor, "record_alert") as mock_alert:
            with patch("payment_callback_enhanced.logger"):
                monitor.check_queue_status()
                mock_alert.assert_called_once()
                call_args = mock_alert.call_args[0]
                assert call_args[1] == "warning"

    def test_check_queue_status_critical(self, monitor):
        from payment_callback_enhanced import PaymentRetryRecord
        with monitor.retry_lock:
            for i in range(95):
                monitor.retry_queue.append(
                    PaymentRetryRecord(
                        order_id=f"order{i}",
                        retry_count=0,
                        first_attempt_time=time.time(),
                        last_attempt_time=time.time(),
                        next_retry_time=time.time() + 60,
                    )
                )
        with patch.object(monitor, "record_alert") as mock_alert:
            with patch("payment_callback_enhanced.logger"):
                monitor.check_queue_status()
                mock_alert.assert_called_once()
                call_args = mock_alert.call_args[0]
                assert call_args[1] == "critical"

    def test_check_failure_rate_normal(self, monitor):
        monitor.stats["processed"] = 100
        monitor.stats["failed"] = 5
        with patch.object(monitor, "record_alert") as mock_alert:
            monitor.check_failure_rate()
            mock_alert.assert_not_called()

    def test_check_failure_rate_high(self, monitor):
        monitor.stats["processed"] = 100
        monitor.stats["failed"] = 15
        with patch.object(monitor, "record_alert") as mock_alert:
            with patch("payment_callback_enhanced.logger"):
                monitor.check_failure_rate()
                mock_alert.assert_called_once()
                call_args = mock_alert.call_args[0]
                assert call_args[0] == "high_failure_rate"

    def test_check_failure_rate_no_data(self, monitor):
        monitor.stats["processed"] = 0
        monitor.stats["failed"] = 0
        with patch.object(monitor, "record_alert") as mock_alert:
            monitor.check_failure_rate()
            mock_alert.assert_not_called()

    def test_record_alert_new(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor.__class__, "send_alert_notification") as mock_send:
                monitor.record_alert("test_type", "warning", "test message", {"key": "value"})
                assert len(monitor.alerts) == 1
                assert monitor.alerts[0].alert_type == "test_type"
                mock_send.assert_called_once()

    def test_record_alert_updates_existing(self, monitor):
        from payment_callback_enhanced import PaymentAlert
        existing = PaymentAlert(
            timestamp=time.time() - 100,
            alert_type="test_type",
            level="warning",
            message="old message",
            stats={},
        )
        monitor.alerts.append(existing)
        with patch("payment_callback_enhanced.logger"):
            with patch("payment_callback_enhanced.PaymentCallbackEnhanced.send_alert_notification") as mock_send:
                monitor.record_alert("test_type", "warning", "new message", {"key": "value"})
                assert len(monitor.alerts) == 1
                assert monitor.alerts[0].message == "new message"
                mock_send.assert_not_called()

    def test_record_alert_limit(self, monitor):
        from payment_callback_enhanced import PaymentAlert
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor, "send_alert_notification"):
                for i in range(150):
                    monitor.alerts.append(PaymentAlert(
                        timestamp=time.time() - i,
                        alert_type=f"type_{i}",
                        level="warning",
                        message=f"message {i}",
                        stats={},
                    ))
                monitor.record_alert("new_type", "warning", "new message", {})
                assert len(monitor.alerts) == 100

    def test_get_stats(self, monitor):
        monitor.stats["processed"] = 10
        monitor.stats["failed"] = 2
        stats = monitor.get_stats()
        assert stats["processed"] == 10
        assert stats["failed"] == 2
        assert stats["queue_size"] == 0

    def test_get_recent_alerts(self, monitor):
        from payment_callback_enhanced import PaymentAlert
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor, "send_alert_notification"):
                for i in range(15):
                    monitor.alerts.append(PaymentAlert(
                        timestamp=time.time() - i,
                        alert_type="test_type",
                        level="warning",
                        message=f"message {i}",
                        stats={},
                    ))
                alerts = monitor.get_recent_alerts(limit=5)
                assert len(alerts) == 5

    def test_get_recent_alerts_unresolved_only(self, monitor):
        from payment_callback_enhanced import PaymentAlert
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor, "send_alert_notification"):
                monitor.alerts.append(PaymentAlert(
                    timestamp=time.time(),
                    alert_type="test_type",
                    level="warning",
                    message="unresolved",
                    stats={},
                    resolved=False,
                ))
                monitor.alerts.append(PaymentAlert(
                    timestamp=time.time() - 1,
                    alert_type="test_type",
                    level="warning",
                    message="resolved",
                    stats={},
                    resolved=True,
                ))
                alerts = monitor.get_recent_alerts(unresolved_only=True)
                assert len(alerts) == 1
                assert alerts[0]["message"] == "unresolved"

    def test_start_monitoring_already_running(self, monitor):
        monitor.monitoring = True
        with patch("payment_callback_enhanced.logger"):
            monitor.start_monitoring()
            assert monitor.monitoring is True

    def test_start_monitoring(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            with patch.object(monitor, "_monitor_loop"):
                monitor.start_monitoring()
                assert monitor.monitoring is True
                monitor.stop_monitoring()

    def test_stop_monitoring(self, monitor):
        with patch("payment_callback_enhanced.logger"):
            monitor.monitoring = True
            monitor._stop_event.set()
            monitor.monitor_thread = MagicMock()
            monitor.stop_monitoring()
            assert monitor.monitoring is False

    def test_check_and_monitor(self, monitor):
        with patch.object(monitor, "check_queue_status") as mock_queue:
            with patch.object(monitor, "check_failure_rate") as mock_failure:
                with patch.object(monitor, "process_retry_queue") as mock_retry:
                    with patch("payment_callback_enhanced.logger"):
                        monitor.check_and_monitor()
                        mock_queue.assert_called_once()
                        mock_failure.assert_called_once()
                        mock_retry.assert_called_once()


class TestPaymentRetryRecord:
    def test_record_creation(self):
        from payment_callback_enhanced import PaymentRetryRecord
        record = PaymentRetryRecord(
            order_id="order1",
            retry_count=0,
            first_attempt_time=time.time(),
            last_attempt_time=time.time(),
            next_retry_time=time.time() + 60,
            error_message=None,
            max_retries=3,
        )
        assert record.order_id == "order1"
        assert record.retry_count == 0
        assert record.max_retries == 3


class TestPaymentAlert:
    def test_alert_creation(self):
        from payment_callback_enhanced import PaymentAlert
        alert = PaymentAlert(
            timestamp=time.time(),
            alert_type="test",
            level="warning",
            message="test message",
            stats={"key": "value"},
        )
        assert alert.alert_type == "test"
        assert alert.level == "warning"
        assert alert.resolved is False
        assert alert.resolved_at is None


class TestGlobalFunctions:
    def test_get_payment_callback_monitor(self):
        import payment_callback_enhanced as pce
        pce._global_payment_monitor = None
        with patch.object(pce, "PaymentCallbackEnhanced") as MockMonitor:
            mock_instance = MagicMock()
            MockMonitor.return_value = mock_instance
            result = pce.get_payment_callback_monitor()
            assert result == mock_instance
            mock_instance.start_monitoring.assert_called_once()

    def test_stop_payment_callback_monitor(self):
        import payment_callback_enhanced as pce
        mock_monitor = MagicMock()
        pce._global_payment_monitor = mock_monitor
        pce.stop_payment_callback_monitor()
        mock_monitor.stop_monitoring.assert_called_once()
        assert pce._global_payment_monitor is None

    def test_stop_payment_callback_monitor_not_started(self):
        import payment_callback_enhanced as pce
        pce._global_payment_monitor = None
        with patch("payment_callback_enhanced.logger"):
            pce.stop_payment_callback_monitor()
