from telethon import TelegramClient
import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta

# ========== 容器适配：强制关闭输出缓冲（核心） ==========
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ========== 固定配置 ==========
API_ID = 你申请的API_ID
API_HASH = '你申请的API_HASH'
CHANNEL_ID = '@你需要发送指令的机器人ID'
SESSION_PATH = '/app/chat_name.session'

# ========== 间隔配置 ==========
CHECKIN_INTERVAL_HOURS = 24  # checkin每24小时执行
UPGRADE_INTERVAL_HOURS = 71  # upgrade每71小时执行

# ========== 持久化文件 ==========
START_BASE_TIME_FILE = '/app/start_base_time.txt'  # 脚本首次运行基准时间
UPGRADE_RECORD_FILE = '/app/upgrade_record.txt'     # upgrade执行记录
CHECKIN_RECORD_FILE = '/app/checkin_record.txt'     # checkin执行记录


async def send_checkin():
    """发送/checkin指令（每24小时）"""
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        try:
            await client.send_message(CHANNEL_ID, '/checkin')
            logger.info(f"已发送签到指令: /checkin ©Jeffern")
            # 记录本次checkin执行时间
            try:
                with open(CHECKIN_RECORD_FILE, 'w') as f:
                    f.write(str(datetime.now().timestamp()))
                logger.debug(f"已更新checkin执行记录到 {CHECKIN_RECORD_FILE}")
            except Exception as file_e:
                logger.warning(f"记录checkin执行时间失败（不影响核心功能）: {str(file_e)}")
        except Exception as e:
            logger.error(f"发送/checkin指令失败: {str(e)}", exc_info=True)
            raise


async def send_upgrade():
    """发送/upgrade指令（每71小时）"""
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        try:
            await client.send_message(CHANNEL_ID, '/upgrade')
            logger.info(f"已发送升级指令: /upgrade ©Jeffern")
            # 记录本次upgrade执行时间
            try:
                with open(UPGRADE_RECORD_FILE, 'w') as f:
                    f.write(str(datetime.now().timestamp()))
                logger.debug(f"已更新upgrade执行记录到 {UPGRADE_RECORD_FILE}")
            except Exception as file_e:
                logger.warning(f"记录upgrade执行时间失败（不影响核心功能）: {str(file_e)}")
        except Exception as e:
            logger.error(f"发送/upgrade指令失败: {str(e)}", exc_info=True)
            raise


def get_start_base_time():
    """获取脚本首次运行的基准时间（核心：所有计时基于此时间）"""
    try:
        with open(START_BASE_TIME_FILE, 'r') as f:
            timestamp = float(f.read().strip())
            base_time = datetime.fromtimestamp(timestamp)
            logger.info(f"读取到脚本首次运行基准时间: {base_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return base_time
    except FileNotFoundError:
        # 首次运行：记录当前时间作为基准时间
        base_time = datetime.now()
        try:
            with open(START_BASE_TIME_FILE, 'w') as f:
                f.write(str(base_time.timestamp()))
            logger.info(f"首次运行，记录基准时间: {base_time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as file_e:
            logger.error(f"记录基准时间失败（程序可能异常）: {str(file_e)}")
            raise
        return base_time
    except (ValueError, PermissionError) as e:
        logger.error(f"读取基准时间失败，程序无法继续: {str(e)}")
        raise


def get_last_exec_time(record_file, interval_hours, base_time):
    """获取指令上次执行时间（容错：无记录则返回基准时间）"""
    try:
        with open(record_file, 'r') as f:
            timestamp = float(f.read().strip())
            last_time = datetime.fromtimestamp(timestamp)
            logger.info(f"读取到{record_file}上次执行时间: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return last_time
    except FileNotFoundError:
        # 无执行记录：返回基准时间（首次执行）
        logger.info(f"未找到{record_file}执行记录，首次执行（基准时间）")
        return base_time
    except (ValueError, PermissionError) as e:
        logger.warning(f"读取{record_file}执行记录失败，使用基准时间: {str(e)}")
        return base_time


def calculate_next_exec_seconds(base_time, last_exec_time, interval_hours):
    """计算距离下次执行的休眠秒数（基于基准时间的固定间隔）"""
    now = datetime.now()
    # 计算从基准时间到现在的总小时数
    total_hours_since_base = (now - base_time).total_seconds() / 3600
    # 计算该指令应执行的次数：总小时数 / 间隔小时数（向上取整）
    exec_count = int(total_hours_since_base // interval_hours) + 1
    # 下次执行时间 = 基准时间 + 执行次数 * 间隔小时数
    next_exec_time = base_time + timedelta(hours=exec_count * interval_hours)
    
    # 容错：如果上次执行时间晚于计算出的下次执行时间（如程序重启），重新计算
    if last_exec_time > next_exec_time:
        last_exec_hours = (last_exec_time - base_time).total_seconds() / 3600
        exec_count = int(last_exec_hours // interval_hours) + 1
        next_exec_time = base_time + timedelta(hours=exec_count * interval_hours)
    
    # 计算休眠秒数（最小为0，立即执行）
    sleep_seconds = max(0, (next_exec_time - now).total_seconds())
    logger.info(f"距离下次执行（间隔{interval_hours}H）还有 {sleep_seconds/3600:.2f} 小时，目标时间: {next_exec_time.strftime('%Y-%m-%d %H:%M:%S')}")
    return sleep_seconds


async def main():
    """主循环：基于首次运行时间的固定间隔执行"""
    logger.info(f"启动Telegram自动脚本 | checkin每{CHECKIN_INTERVAL_HOURS}H | upgrade每{UPGRADE_INTERVAL_HOURS}H（计时基于脚本首次运行时间）")
    
    # 检查核心文件
    if not os.path.exists(SESSION_PATH):
        logger.error(f"Session文件不存在: {SESSION_PATH}，请确认文件已挂载到容器")
        raise FileNotFoundError(f"Missing session file: {SESSION_PATH}")

    # 获取基准时间（脚本首次运行时间）
    base_time = get_start_base_time()

    # ========== 新增：首次运行立即执行两条指令 ==========
    is_first_run = not (os.path.exists(CHECKIN_RECORD_FILE) and os.path.exists(UPGRADE_RECORD_FILE))
    if is_first_run:
        logger.info("检测到首次运行，立即发送checkin和upgrade指令")
        try:
            await send_checkin()
            await send_upgrade()
        except Exception as e:
            logger.error(f"首次执行指令失败: {str(e)}", exc_info=True)
            # 首次执行失败仍继续运行，后续会按间隔重试
            pass

    while True:
        try:
            # ========== 处理checkin指令 ==========
            last_checkin = get_last_exec_time(CHECKIN_RECORD_FILE, CHECKIN_INTERVAL_HOURS, base_time)
            checkin_sleep = calculate_next_exec_seconds(base_time, last_checkin, CHECKIN_INTERVAL_HOURS)
            
            # ========== 处理upgrade指令 ==========
            last_upgrade = get_last_exec_time(UPGRADE_RECORD_FILE, UPGRADE_INTERVAL_HOURS, base_time)
            upgrade_sleep = calculate_next_exec_seconds(base_time, last_upgrade, UPGRADE_INTERVAL_HOURS)
            
            # ========== 休眠到最近的任务执行时间 ==========
            next_sleep = min(checkin_sleep, upgrade_sleep)
            # 每小时打印心跳（监控用）
            for _ in range(int(next_sleep) // 3600):
                await asyncio.sleep(3600)
                logger.info("程序运行中，等待下次任务执行...")
            # 休眠剩余不足1小时的部分
            await asyncio.sleep(next_sleep % 3600)
            
            # ========== 执行到期的任务 ==========
            now = datetime.now()
            # 检查checkin是否到期
            if (now - last_checkin).total_seconds() >= CHECKIN_INTERVAL_HOURS * 3600:
                await send_checkin()
            # 检查upgrade是否到期
            if (now - last_upgrade).total_seconds() >= UPGRADE_INTERVAL_HOURS * 3600:
                await send_upgrade()

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
