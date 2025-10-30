# -*- coding: utf-8 -*-
"""
微信支付回调接收服务器（带异步处理队列）
用于接收微信支付的异步通知
"""

from flask import Flask, request, jsonify
import logging
import threading
from queue import Queue
from payment_handler import payment_handler, PaymentHandler
from utils import mask_sensitive

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==================== 异步处理队列 ====================
# 创建支付处理队列
payment_processing_queue = Queue(maxsize=1000)

# 队列统计信息
queue_stats = {
    'processed': 0,
    'failed': 0,
    'pending': 0
}


def payment_worker():
    """
    后台工作线程：处理支付成功的业务逻辑
    这样可以快速响应微信回调（<1秒），避免超时
    """
    logger.info("支付处理工作线程已启动")
    while True:
        try:
            # 阻塞等待队列中的订单
            order_id = payment_processing_queue.get()
            queue_stats['pending'] = payment_processing_queue.qsize()

            logger.info(f"开始处理订单: {mask_sensitive(order_id, 'order_id')}")

            # 处理支付成功业务逻辑（更新用户套餐等）
            try:
                PaymentHandler.handle_payment_success(order_id)
                queue_stats['processed'] += 1
                logger.info(
                    f"✅ 订单处理成功: {mask_sensitive(order_id, 'order_id')}"
                )
            except Exception as e:
                queue_stats['failed'] += 1
                logger.error(
                    f"❌ 订单处理失败: "
                    f"{mask_sensitive(order_id, 'order_id')}, 错误: {e}"
                )
                # 失败的订单会由补偿服务重试

            # 标记任务完成
            payment_processing_queue.task_done()

        except Exception as e:
            logger.error(f"支付工作线程异常: {e}")


# 启动2个工作线程（提高处理能力）
for i in range(2):
    worker = threading.Thread(
        target=payment_worker,
        daemon=True,
        name=f"PaymentWorker-{i + 1}"
    )
    worker.start()
    logger.info(f"工作线程 {i + 1} 已启动")
# ====================================================


@app.route('/wechat/notify', methods=['POST'])
def wechat_notify():
    """
    接收微信支付回调通知（v3 API）
    策略：快速验证签名 → 立即响应 → 异步处理业务逻辑
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
        logger.info("收到微信支付通知")

        # 构建通知数据
        notify_data = {
            'headers': headers,
            'body': body
        }

        # ========== 阶段1：快速验证签名（目标<500ms）==========
        result = payment_handler.process_wechat_notify(notify_data)

        if not result['success']:
            # 签名验证失败，立即返回错误
            logger.error(f"签名验证失败: {result['message']}")
            return jsonify({
                'code': 'FAIL',
                'message': result['message']
            }), 400

        # ========== 阶段2：提取订单号，放入队列 ==========
        order_id = result.get('out_trade_no')
        if not order_id:
            logger.error("未能从回调中提取订单号")
            return jsonify({
                'code': 'FAIL',
                'message': '订单号缺失'
            }), 400

        # 更新订单状态为PAID（轻量级数据库操作）
        try:
            PaymentHandler.update_order_status(order_id, "PAID")
        except Exception as e:
            logger.error(f"更新订单状态失败: {e}")
            # 即使更新失败，也继续放入队列，补偿服务会处理

        # 放入异步处理队列
        try:
            payment_processing_queue.put_nowait(order_id)
            logger.info(
                f"订单已放入处理队列: "
                f"{mask_sensitive(order_id, 'order_id')}, "
                f"队列长度: {payment_processing_queue.qsize()}"
            )
        except Exception as e:
            logger.error(f"放入队列失败: {e}")
            # 即使放入队列失败，补偿服务也会处理

        # ========== 阶段3：立即返回成功响应（总耗时<1秒）==========
        return jsonify({
            'code': 'SUCCESS',
            'message': 'OK'
        }), 200

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
    检查项：
    1. 服务基本响应
    2. 数据库连接
    3. 队列健康状态
    4. 工作线程状态
    """
    import time
    import sqlite3

    health_status = {
        'status': 'healthy',
        'checks': {},
        'timestamp': int(time.time())
    }

    # 1. 检查数据库连接
    try:
        from db_adapter import get_db_connection
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT 1")
            health_status['checks']['database'] = {
                'status': 'healthy',
                'message': '数据库连接正常'
            }
    except (ImportError, sqlite3.Error, OSError) as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'数据库连接失败: {str(e)}'
        }

    # 2. 检查队列状态
    queue_size = payment_processing_queue.qsize()
    if queue_size < 100:
        health_status['checks']['queue'] = {
            'status': 'healthy',
            'size': queue_size,
            'message': '队列状态正常'
        }
    elif queue_size < 500:
        health_status['status'] = 'degraded'
        health_status['checks']['queue'] = {
            'status': 'warning',
            'size': queue_size,
            'message': f'队列积压 ({queue_size})'
        }
    else:
        health_status['status'] = 'unhealthy'
        health_status['checks']['queue'] = {
            'status': 'critical',
            'size': queue_size,
            'message': f'队列严重积压 ({queue_size})'
        }

    # 3. 检查工作线程状态
    active_threads = [t for t in threading.enumerate()
                      if t.name.startswith('PaymentWorker')]
    if len(active_threads) >= 1:
        health_status['checks']['workers'] = {
            'status': 'healthy',
            'active_count': len(active_threads),
            'message': f'{len(active_threads)}个工作线程运行中'
        }
    else:
        health_status['status'] = 'unhealthy'
        health_status['checks']['workers'] = {
            'status': 'unhealthy',
            'active_count': 0,
            'message': '没有活跃的工作线程'
        }

    # 4. 处理统计
    health_status['stats'] = {
        'processed_total': queue_stats['processed'],
        'failed_total': queue_stats['failed'],
        'pending': queue_stats['pending']
    }

    # 根据健康状态返回不同的HTTP状态码
    http_status = 200
    if health_status['status'] == 'unhealthy':
        http_status = 503  # Service Unavailable
    elif health_status['status'] == 'degraded':
        http_status = 200  # 降级但仍可用

    return jsonify(health_status), http_status


@app.route('/queue/stats')
def queue_stats_endpoint():
    """
    队列统计接口（用于监控）
    """
    queue_size = payment_processing_queue.qsize()
    status = 'healthy' if queue_size < 100 else 'warning'
    return jsonify({
        'queue_size': queue_size,
        'processed_total': queue_stats['processed'],
        'failed_total': queue_stats['failed'],
        'pending': queue_stats['pending'],
        'status': status
    })


if __name__ == '__main__':
    # 在生产环境中，建议使用 gunicorn 等 WSGI 服务器
    # 微信支付回调需要接受外网请求，必须绑定0.0.0.0
    app.run(host='0.0.0.0', port=8081, debug=False)  # nosec B104
