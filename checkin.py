from telethon import TelegramClient
import asyncio
import time
import sys
import os
import logging
from datetime import datetime, timedelta
import pytz  # 处理北京时间时区

# ========== 容器适配：强制关闭输出缓冲（核心） ==========
# 确保print/logging内容实时输出到Clawcloud日志
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# ========== 日志配置（替代print，适配Clawcloud日志采集） ==========
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',  # 标准化时间格式
    handlers=[logging.StreamHandler(sys.stdout)]  # 强制输出到标准流
)
logger = logging.getLogger(__name__)

# ========== 固定配置（无需修改） ==========
API_ID = 你申请的TG ID
API_HASH = '你申请的TG HASH'
CHANNEL_ID = '@你的机器人ID'
# session文件路径（镜像内固定路径）
SESSION_PATH = '/app/chat_name.session'
# 时区：北京时间（UTC+8）
CST = pytz.timezone('Asia/Shanghai')

# ========== 定时规则（已按要求配置） ==========
# checkin：每天北京时间0:01
CHECKIN_HOUR = 0
CHECKIN_MINUTE = 1
# upgrade：每71小时发送一次
UPGRADE_INTERVAL_HOURS = 71
# 记录upgrade上次执行时间（持久化到文件，避免容器重启丢失）
UPGRADE_RECORD_FILE = '/app/upgrade_record.txt'


async def send_checkin():
    """发送/checkin指令（每日0:01）"""
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        try:
            await client.send_message(CHANNEL_ID, '/checkin')
            logger.info(f"已发送每日签到指令: /checkin")
        except Exception as e:
            logger.error(f"发送/checkin指令失败: {str(e)}", exc_info=True)
            raise


async def send_upgrade():
    """发送/upgrade指令（每71小时）"""
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        try:
            await client.send_message(CHANNEL_ID, '/upgrade')
            logger.info(f"已发送升级指令: /upgrade")
            # 记录本次执行时间（增加异常处理，适配容器文件权限）
            try:
                with open(UPGRADE_RECORD_FILE, 'w') as f:
                    f.write(str(datetime.now().timestamp()))
                logger.debug(f"已更新upgrade执行记录到 {UPGRADE_RECORD_FILE}")
            except Exception as file_e:
                logger.warning(f"记录upgrade执行时间失败（不影响核心功能）: {str(file_e)}")
        except Exception as e:
            logger.error(f"发送/upgrade指令失败: {str(e)}", exc_info=True)
            raise


def get_last_upgrade_time():
    """获取upgrade上次执行时间（无则返回当前时间-71小时）"""
    try:
        with open(UPGRADE_RECORD_FILE, 'r') as f:
            timestamp = float(f.read().strip())
            last_time = datetime.fromtimestamp(timestamp)
            logger.info(f"读取到upgrade上次执行时间: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return last_time
    except FileNotFoundError:
        # 首次运行：返回71小时前，确保立即执行一次
        default_time = datetime.now() - timedelta(hours=UPGRADE_INTERVAL_HOURS)
        logger.info(f"未找到upgrade执行记录，默认首次执行（上次时间: {default_time.strftime('%Y-%m-%d %H:%M:%S')}）")
        return default_time
    except (ValueError, PermissionError) as e:
        logger.warning(f"读取upgrade执行记录失败，使用默认时间: {str(e)}")
        return datetime.now() - timedelta(hours=UPGRADE_INTERVAL_HOURS)


async def calculate_checkin_sleep_time():
    """计算距离下次checkin的休眠时间（秒）"""
    now = datetime.now(CST)
    # 今天0:01的目标时间（带时区）
    target = now.replace(hour=CHECKIN_HOUR, minute=CHECKIN_MINUTE, second=0, microsecond=0)
    if now > target:
        target += timedelta(days=1)  # 已过则顺延到明天
    sleep_seconds = (target - now).total_seconds()
    logger.info(f"距离下次checkin还有 {sleep_seconds / 3600:.2f} 小时（目标时间: {target.strftime('%Y-%m-%d %H:%M:%S')}）")
    return sleep_seconds


async def main():
    """主循环：定时执行"""
    logger.info(f"启动Telegram自动脚本 | checkin每日{CHECKIN_HOUR}:{CHECKIN_MINUTE} | upgrade每{UPGRADE_INTERVAL_HOURS}小时")
    
    # 检查核心文件是否存在
    if not os.path.exists(SESSION_PATH):
        logger.error(f"Session文件不存在: {SESSION_PATH}，请确认文件已挂载到容器")
        raise FileNotFoundError(f"Missing session file: {SESSION_PATH}")

    while True:
        try:
            # 1. 执行每日checkin
            await send_checkin()

            # 2. 检查是否需要执行upgrade
            last_upgrade = get_last_upgrade_time()
            now = datetime.now()
            if (now - last_upgrade).total_seconds() >= UPGRADE_INTERVAL_HOURS * 3600:
                await send_upgrade()
            else:
                remaining_hours = (UPGRADE_INTERVAL_HOURS * 3600 - (now - last_upgrade).total_seconds()) / 3600
                logger.info(f"暂不执行upgrade，距离下次执行还有 {remaining_hours:.2f} 小时")

            # 3. 休眠到下次checkin时间（每小时打印心跳，便于Clawcloud监控）
            sleep_seconds = await calculate_checkin_sleep_time()
            # 每小时打印一次心跳，避免Clawcloud认为程序无响应
            for _ in range(int(sleep_seconds) // 3600):
                await asyncio.sleep(3600)
                logger.info("程序运行中，等待下次签到...")
            # 休眠剩余不足1小时的部分
            await asyncio.sleep(sleep_seconds % 3600)

        except Exception as e:
            logger.error(f"程序执行异常，5分钟后重试: {str(e)}", exc_info=True)
            await asyncio.sleep(300)  # 异常后5分钟重试


if __name__ == '__main__':
    # 前置校验
    if not API_ID or not API_HASH:
        logger.fatal("API_ID或API_HASH未配置，请检查配置项")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被手动终止")
        sys.exit(0)
    except Exception as e:
        logger.fatal(f"程序致命错误，退出执行: {str(e)}", exc_info=True)
        sys.exit(1)


