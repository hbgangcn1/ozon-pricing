# -*- coding: utf-8 -*-
"""
微信支付回调接收服务器
用于接收微信支付的异步通知
"""

from flask import Flask, request, jsonify
import logging
from payment_handler import payment_handler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/wechat/notify', methods=['POST'])
def wechat_notify():
    """
    接收微信支付回调通知（v3 API）
    """
    try:
        # 获取请求头信息
        headers = {
            'Wechatpay-Timestamp': request.headers.get(
                'Wechatpay-Timestamp', ''
            ),
            'Wechatpay-Nonce': request.headers.get('Wechatpay-Nonce', ''),
            'Wechatpay-Signature': request.headers.get(
                'Wechatpay-Signature', ''
            ),
        }

        # 获取请求体
        body = request.get_data(as_text=True)
        logger.info(f"收到微信支付通知: {body}")

        # 构建通知数据
        notify_data = {
            'headers': headers,
            'body': body
        }

        # 处理通知
        result = payment_handler.process_wechat_notify(notify_data)

        if result['success']:
            # 返回成功响应
            return jsonify({
                'code': 'SUCCESS',
                'message': 'OK'
            }), 200
        else:
            # 返回失败响应
            logger.error(f"支付通知处理失败: {result['message']}")
            return jsonify({
                'code': 'FAIL',
                'message': result['message']
            }), 400

    except Exception as e:
        logger.error(f"处理微信支付通知异常: {str(e)}")
        return jsonify({
            'code': 'FAIL',
            'message': f'系统错误: {str(e)}'
        }), 500


@app.route('/payment/success')
def payment_success():
    """
    支付成功页面
    """
    return """
    <html>
    <head>
        <title>支付成功</title>
        <meta charset="utf-8">
    </head>
    <body style="text-align: center; padding: 50px;">
        <h1>🎉 支付成功！</h1>
        <p>您的订阅已激活，请返回应用查看。</p>
        <p><a href="javascript:history.back()">返回应用</a></p>
    </body>
    </html>
    """


@app.route('/health')
def health_check():
    """
    健康检查接口
    """
    return {"status": "ok", "message": "微信支付回调服务运行正常"}


if __name__ == '__main__':
    # 在生产环境中，建议使用 gunicorn 等 WSGI 服务器
    app.run(host='0.0.0.0', port=8080, debug=False)
