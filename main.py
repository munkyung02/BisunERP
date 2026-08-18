import ctypes
from tkinter import messagebox

from app.main_window import MainWindow
from core.database import initialize_database


SINGLE_INSTANCE_MUTEX_NAME = "BisunERP_v2_8_SingleInstance"
ERROR_ALREADY_EXISTS = 183


def _acquire_single_instance_mutex() -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p,
    )
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool

    mutex_handle = kernel32.CreateMutexW(
        None,
        False,
        SINGLE_INSTANCE_MUTEX_NAME,
    )
    if not mutex_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex_handle)
        return None

    return int(mutex_handle)


def _release_single_instance_mutex(mutex_handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.CloseHandle(mutex_handle)


def _show_already_running_message() -> None:
    try:
        messagebox.showinfo(
            "비선 ERP",
            "비선 ERP가 이미 실행 중입니다.",
        )
    except Exception:
        pass


def main() -> None:
    mutex_handle = _acquire_single_instance_mutex()
    if mutex_handle is None:
        _show_already_running_message()
        return

    try:
        database = initialize_database()

        print("=" * 55)
        print("비선상회 ERP 데이터베이스 준비 완료")
        print(f"DB 위치: {database.database_path}")
        print("생성된 테이블:")

        for table_name in database.get_table_names():
            print(f"- {table_name}")

        print("=" * 55)

        # 자동 백업, Notion 자동동기화, 쿠팡 주문 스케줄러는
        # MainWindow가 한 번씩만 생성하고 관리합니다.
        app = MainWindow()
        app.run()

    except Exception as error:
        messagebox.showerror(
            "ERP 시작 오류",
            "비선상회 ERP를 시작하지 못했습니다.\n\n"
            f"오류 내용: {error}",
        )
        raise
    finally:
        _release_single_instance_mutex(mutex_handle)


if __name__ == "__main__":
    main()
