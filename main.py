from tkinter import messagebox

from app.main_window import MainWindow
from core.database import initialize_database


def main() -> None:
    try:
        database = initialize_database()

        print("=" * 55)
        print("비선상회 ERP 데이터베이스 준비 완료")
        print(f"DB 위치: {database.database_path}")
        print("생성된 테이블:")

        for table_name in database.get_table_names():
            print(f"- {table_name}")

        print("=" * 55)

        app = MainWindow()
        app.run()

    except Exception as error:
        messagebox.showerror(
            "ERP 시작 오류",
            "비선상회 ERP를 시작하지 못했습니다.\n\n"
            f"오류 내용: {error}",
        )

        raise


if __name__ == "__main__":
    main()
    