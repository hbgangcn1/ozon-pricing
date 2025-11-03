# -*- coding: utf-8 -*-
"""
支付成功页面测试
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from payment_success_page import (
    show_payment_success_page,
    show_payment_processing_page,
)


class MockSessionState:
    """Mock SessionState对象，支持属性访问和字典访问"""
    def __init__(self):
        self._data = {}
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __contains__(self, key):
        return key in self._data
    
    def __getattr__(self, name):
        return self._data.get(name)
    
    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            if not hasattr(self, '_data'):
                super().__setattr__('_data', {})
            self._data[name] = value
    
    def keys(self):
        return self._data.keys()
    
    def get(self, key, default=None):
        return self._data.get(key, default)


class TestShowPaymentSuccessPage:
    """测试显示支付成功页面"""

    @patch('payment_success_page.st')
    def test_show_payment_success_page_with_order_id(self, mock_st):
        """测试显示支付成功页面（带订单ID）"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        show_payment_success_page(order_id="test_order_123", plan_name="效率版")
        
        # 验证调用了title和success
        assert mock_st.title.called
        assert mock_st.success.called
        # 验证显示了订单信息
        assert mock_st.info.called

    @patch('payment_success_page.st')
    def test_show_payment_success_page_without_order_id(self, mock_st):
        """测试显示支付成功页面（无订单ID）"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        show_payment_success_page()
        
        assert mock_st.title.called
        assert mock_st.success.called

    @patch('payment_success_page.st')
    @patch('payment_success_page.get_user_subscription_info')
    def test_show_payment_success_page_with_subscription(self, mock_get_sub, mock_st):
        """测试显示支付成功页面（有订阅信息）"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.user_id = 1
        mock_st.rerun = MagicMock()
        
        # Mock订阅信息
        mock_get_sub.return_value = {
            'subscription_type': 'efficiency',
            'subscription_expires': int(time.time()) + 86400,
            'calculations_remaining': -1
        }
        
        show_payment_success_page(order_id="test_order")
        
        assert mock_st.subheader.called
        assert mock_st.metric.called

    @patch('payment_success_page.st')
    @patch('payment_success_page.get_user_subscription_info')
    def test_show_payment_success_page_without_subscription(self, mock_get_sub, mock_st):
        """测试显示支付成功页面（无订阅信息）"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.user_id = 1
        mock_st.rerun = MagicMock()
        
        mock_get_sub.return_value = None
        
        show_payment_success_page(order_id="test_order")
        
        assert mock_st.title.called

    @patch('payment_success_page.st')
    def test_show_payment_success_page_refresh_button(self, mock_st):
        """测试刷新页面按钮"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(side_effect=[True, False, False])
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        show_payment_success_page()
        
        # 验证调用了rerun
        assert mock_st.rerun.called

    @patch('payment_success_page.st')
    def test_show_payment_success_page_auto_refresh_countdown(self, mock_st):
        """测试自动刷新倒计时"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.auto_refresh_countdown = 5
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_success_page()
        
        # 验证倒计时减少
        assert mock_st.session_state.auto_refresh_countdown == 4

    @patch('payment_success_page.st')
    def test_show_payment_success_page_auto_refresh_complete(self, mock_st):
        """测试自动刷新完成"""
        mock_st.title = MagicMock()
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[
            MagicMock(), MagicMock(), MagicMock()
        ])
        mock_st.metric = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.switch_page = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.auto_refresh_countdown = 0
        mock_st.rerun = MagicMock()
        
        show_payment_success_page()
        
        # 验证最后调用了rerun
        assert mock_st.rerun.called


class TestShowPaymentProcessingPage:
    """测试显示支付处理中页面"""

    @patch('payment_success_page.st')
    def test_show_payment_processing_page_basic(self, mock_st):
        """测试显示支付处理中页面（基本功能）"""
        mock_st.title = MagicMock()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_processing_page("test_order_123", "效率版")
        
        assert mock_st.title.called
        assert mock_st.info.called

    @patch('payment_success_page.st')
    @patch('payment_success_page.show_payment_success_page')
    def test_show_payment_processing_page_success(self, mock_show_success, mock_st):
        """测试支付处理中页面（支付成功）"""
        mock_st.title = MagicMock()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.success = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_check_count = 3
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_processing_page("test_order_123", "效率版")
        
        # 验证调用了成功页面
        assert mock_show_success.called

    @patch('payment_success_page.st')
    def test_show_payment_processing_page_checking(self, mock_st):
        """测试支付处理中页面（检查中）"""
        mock_st.title = MagicMock()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_check_count = 1
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_processing_page("test_order_123")
        
        assert mock_st.warning.called
        assert "处理中" in str(mock_st.warning.call_args)

    @patch('payment_success_page.st')
    def test_show_payment_processing_page_increments_count(self, mock_st):
        """测试支付处理中页面增加检查计数"""
        mock_st.title = MagicMock()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_processing_page("test_order_123")
        
        assert mock_st.session_state.payment_check_count == 1

    @patch('payment_success_page.st')
    def test_show_payment_processing_page_without_plan_name(self, mock_st):
        """测试支付处理中页面（无套餐名称）"""
        mock_st.title = MagicMock()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            show_payment_processing_page("test_order_123")
        
        assert mock_st.title.called

