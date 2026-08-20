from modules.purchases.purchase_service import PurchaseService


def main() -> None:
    cases = [
        (None, "1개 500g", 1, 1),
        (None, "2개 500g", 1, 2),
        (None, "2개 500g", 3, 6),
        (None, "3팩", 1, 3),
        (None, "2세트", 2, 4),
        (None, "500g", 1, 1),
        (None, "1kg", 2, 2),
        (None, "등살 뱃살 꼬릿살", 1, 1),
        (None, "2개입 500g", 1, 2),
        ("Gmarket", "전어 회필렛 250g/1500원/2개", 2, 2),
        ("Auction", "전어 회필렛 250g/1500원/3개", 3, 3),
        ("쿠팡", "4개 200g(14미 내외)", 1, 4),
        ("Toss", "2개, 100", 1, 2),
        ("스마트스토어", "단일상품", 2, 2),
        ("LotteOn", "단일상품", 2, 2),
        ("Kakao", None, 2, 2),
    ]

    failed = []

    for platform, option_name, order_quantity, expected in cases:
        actual = PurchaseService._purchase_quantity(
            order_quantity,
            option_name,
            platform=platform,
        )

        status = "PASS" if actual == expected else "FAIL"
        print(
            f"[{status}] 플랫폼={platform!r}, 주문수량={order_quantity}, "
            f"옵션={option_name!r} -> 발주수량={actual}, "
            f"기대={expected}"
        )

        if actual != expected:
            failed.append(
                (platform, option_name, order_quantity, expected, actual)
            )

    print()
    if failed:
        print(f"FAIL {len(failed)}건")
        raise SystemExit(1)

    print(f"PASS {len(cases)}건")
    print("옵션 수량 계산 테스트를 통과했습니다.")


if __name__ == "__main__":
    main()
