#!/bin/bash

echo "启动生产环境 - 使用 Gunicorn"
echo

# 设置生产环境模式
export PRODUCTION_MODE=true

echo "当前配置："
echo "- 生产环境模式: $PRODUCTION_MODE"
echo "- 域名: https://www.cbprice.cn"
echo "- 回调地址: https://www.cbprice.cn/wechat/notify"
echo "- 返回地址: https://www.cbprice.cn/payment/success"
echo

echo "请选择启动方式："
echo "1. 启动主应用 (Streamlit - 端口8501)"
echo "2. 启动回调服务器 (Gunicorn - 端口8081)"  
echo "3. 同时启动主应用和回调服务器"
echo "0. 退出"

read -p "请输入选择 (0-3): " choice

case $choice in
    1)
        echo
        echo "启动主应用..."
        echo "访问地址: http://localhost:8501"
        echo
        streamlit run app.py --server.port 8501
        ;;
    2)
        echo
        echo "启动回调服务器 (Gunicorn)..."
        echo "回调地址: http://localhost:8081"
        echo
        gunicorn -w 4 -b 0.0.0.0:8081 app:app
        ;;
    3)
        echo
        echo "同时启动主应用和回调服务器..."
        echo "主应用: http://localhost:8501"
        echo "回调服务: http://localhost:8081"
        echo
        # 启动回调服务器
        gunicorn -w 4 -b 0.0.0.0:8081 app:app &
        GUNICORN_PID=$!
        
        # 等待2秒
        sleep 2
        
        # 启动主应用
        streamlit run app.py --server.port 8501 &
        STREAMLIT_PID=$!
        
        echo "两个服务已启动"
        echo "Gunicorn PID: $GUNICORN_PID"
        echo "Streamlit PID: $STREAMLIT_PID"
        echo "按 Ctrl+C 停止所有服务"
        
        # 等待用户中断
        trap "kill $GUNICORN_PID $STREAMLIT_PID; exit" INT
        wait
        ;;
    0)
        echo "退出"
        ;;
    *)
        echo "无效选择"
        ;;
esac
