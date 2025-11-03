# -*- coding: utf-8 -*-
"""
支付状态管理器测试
"""

import pytest
from unittest.mock import patch, MagicMock
from payment_state_manager import (
    save_payment_state_to_browser,
    restore_payment_state_from_browser,
    clear_payment_state_from_browser,
    update_check_count_in_browser,
)


class TestSavePaymentStateToBrowser:
    """测试保存支付状态到浏览器"""

    @patch('payment_state_manager.components.html')
    def test_save_payment_state_to_browser(self, mock_html):
        """测试保存支付状态到浏览器"""
        order_id = "test_order_123"
        plan_name = "效率版"
        
        save_payment_state_to_browser(order_id, plan_name)
        
        # 验证调用了components.html
        assert mock_html.called
        call_args = mock_html.call_args
        
        # 验证HTML代码包含订单信息
        html_code = call_args[0][0]
        assert order_id in html_code
        assert plan_name in html_code
        assert "localStorage.setItem" in html_code
        assert "current_payment" in html_code

    @patch('payment_state_manager.components.html')
    def test_save_payment_state_different_orders(self, mock_html):
        """测试保存不同订单的状态"""
        save_payment_state_to_browser("order1", "效率版")
        save_payment_state_to_browser("order2", "专业版")
        
        assert mock_html.call_count == 2


class TestRestorePaymentStateFromBrowser:
    """测试从浏览器恢复支付状态"""

    @patch('payment_state_manager.components.html')
    def test_restore_payment_state_from_browser(self, mock_html):
        """测试从浏览器恢复支付状态"""
        restore_payment_state_from_browser()
        
        # 验证调用了components.html
        assert mock_html.called
        call_args = mock_html.call_args
        
        # 验证HTML代码包含恢复逻辑
        html_code = call_args[0][0]
        assert "localStorage.getItem" in html_code
        assert "current_payment" in html_code
        assert "restore_order" in html_code

    @patch('payment_state_manager.components.html')
    def test_restore_payment_state_timeout_check(self, mock_html):
        """测试恢复支付状态时检查超时"""
        restore_payment_state_from_browser()
        
        html_code = mock_html.call_args[0][0]
        # 验证包含30分钟超时检查
        assert "30 * 60 * 1000" in html_code or "1800000" in html_code


class TestClearPaymentStateFromBrowser:
    """测试清除浏览器支付状态"""

    @patch('payment_state_manager.components.html')
    def test_clear_payment_state_from_browser(self, mock_html):
        """测试清除浏览器支付状态"""
        clear_payment_state_from_browser()
        
        # 验证调用了components.html
        assert mock_html.called
        call_args = mock_html.call_args
        
        # 验证HTML代码包含清除逻辑
        html_code = call_args[0][0]
        assert "localStorage.removeItem" in html_code
        assert "current_payment" in html_code


class TestUpdateCheckCountInBrowser:
    """测试更新浏览器中的检查次数"""

    @patch('payment_state_manager.components.html')
    def test_update_check_count_in_browser(self, mock_html):
        """测试更新检查次数"""
        update_check_count_in_browser()
        
        # 验证调用了components.html
        assert mock_html.called
        call_args = mock_html.call_args
        
        # 验证HTML代码包含更新逻辑
        html_code = call_args[0][0]
        assert "auto_check_count" in html_code
        assert "localStorage.getItem" in html_code
        assert "localStorage.setItem" in html_code

    @patch('payment_state_manager.components.html')
    def test_update_check_count_increments(self, mock_html):
        """测试检查次数递增逻辑"""
        update_check_count_in_browser()
        
        html_code = mock_html.call_args[0][0]
        # 验证包含递增逻辑
        assert "+ 1" in html_code or "+= 1" in html_code

