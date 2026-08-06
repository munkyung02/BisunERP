from modules.purchases.purchase_service import PurchaseService


def main() -> None:
    cases = [
        ("1개 500g", 1, 1),
        ("2개 500g", 1, 2),
        ("2개 500g", 3, 6),
        ("3팩", 1, 3),
        ("2세트", 2, 4),
        ("500g", 1, 1),
        ("1kg", 2, 2),
        ("등살 뱃살 꼬릿살", 1, 1),
        ("2개입 500g", 1, 2),
    ]

    failed = []

    for option_name, order_quantity, expected in cases:
        actual = PurchaseService._purchase_quantity(
            order_quantity,
            option_name,
        )

        status = "PASS" if actual == expected else "FAIL"
        print(
            f"[{status}] 주문수량={order_quantity}, "
            f"옵션={option_name!r} -> 발주수량={actual}, "
            f"기대={expected}"
        )

        if actual != expected:
            failed.append(
                (option_name, order_quantity, expected, actual)
            )

    print()
    if failed:
        print(f"FAIL {len(failed)}건")
        raise SystemExit(1)

    print(f"PASS {len(cases)}건")
    print("옵션 수량 계산 테스트를 통과했습니다.")


if __name__ == "__main__":
    main()
