from __future__ import annotations
import random
from .brand_voice import get_brand_voice
from typing import Any

from .product_knowledge import find_product_knowledge


class SectionWriter:
    def write(
        self,
        section: str,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        method = getattr(
            self,
            f"write_{section}",
            self.write_default,
        )

        title, body = method(product, playbook)

        title, body = self.apply_brand_voice(title, body)

        return title, body
    
    def hero_templates(
        self,
        name: str,
        origin: str,
        dna: str,
        usp: str,
    ) -> list[str]:

        return [
            f"{origin}에서 정성껏 준비한 {name}\n{dna}\n{usp}",

            f"{name}의 가장 큰 매력은\n{dna}\n{usp}",

            f"좋은 {name}은 재료부터 다릅니다.\n{origin} 산지의 신선함을 담았습니다.\n{usp}",

            f"오늘 가장 자신 있게 추천하는 {name}\n{dna}\n{usp}",

            f"{origin}의 신선함을 그대로 담은 {name}\n{usp}",
        ]

    @staticmethod
    def value(
        product: dict[str, Any],
        key: str,
        default: str = "",
    ) -> str:
        return str(product.get(key) or default).strip()
    
    def product_name(self, product: dict[str, Any]) -> str:
        return str(
            product.get("display_name")
            or product.get("product_name")
            or "상품"
        ).strip()

    def get_knowledge(
        self,
        product: dict[str, Any],
    ) -> dict[str, Any] | None:
        parts = [
            self.product_name(product),
            self.value(product, "category"),
            self.value(product, "origin"),
            self.value(product, "product_dna"),
        ]

        search = " ".join(
            str(part).strip()
            for part in parts
            if str(part).strip()
        )

        return find_product_knowledge(search)
        
    def get_voice(self):
        return get_brand_voice()

    def write_default(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)

        return name, ""

    def write_brand_intro(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)

        return (
            "오늘은 뭐 먹지?\n비선상회 가보자.",
            (
                f"{name}을 찾다가 들어오셨다면,\n"
                "다음에는 비선상회를 믿고 찾아오실 수 있도록.\n\n"
                "좋은 농수산물은 많지만\n"
                "아무거나 소개하지는 않습니다."
            ),
        )

    def write_hero(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)

        origin = self.value(
            product,
            "origin",
            "좋은 산지",
        )

        dna = self.value(
            product,
            "product_dna",
            "신선함 · 좋은 상태 · 제대로 된 맛",
        )

        hook = self.value(
            product,
            "selected_hook",
            str(playbook.get("hook") or f"제대로 고른 {name}"),
        )

        usp = str(
            playbook.get("usp")
            or self.value(
                product,
                "key_point",
                "상태와 선별 기준을 먼저 확인해 준비했습니다.",
            )
        ).strip()

        body_lines = [
            f"{origin}에서 준비한 {name}",
            dna,
        ]

        if usp and usp not in body_lines:
            body_lines.append(usp)

        body = random.choice(
            self.hero_templates(
                name,
                origin,
                dna,
                usp,
            )
        )

        return (
            hook,
            body,
        )
    
    def write_why_now(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)
        category = self.value(product, "category")
        why_now = self.value(product, "why_now")
        dna = self.value(product, "product_dna")

        knowledge = self.get_knowledge(product)

        why_list = list(
            (knowledge or {}).get("why_now", [])
        )

        search = f"{name} {category} {dna}".lower()

        if why_now:
            return (
                f"왜 지금 {name}일까요?",
                why_now,
            )

        if why_list:
            selected = random.sample(
                why_list,
                k=min(2, len(why_list)),
            )

            return (
                f"왜 지금 {name}일까요?",
                "\n\n".join(selected),
            )
        if any(word in search for word in ["홍게", "대게"]):
            body = (
                "게류는 조업 시기와 수율에 따라 만족도가 크게 달라집니다.\n\n"
                "좋은 원물이 들어오는 시기에 준비한 상품은\n"
                "살의 풍성함과 감칠맛에서 차이를 느낄 수 있습니다."
            )

        elif "꽃게" in search:
            body = (
                "꽃게는 계절에 따라 살과 알의 상태가 달라집니다.\n\n"
                "제철에 가까울수록 풍미와 식감이 좋아져\n"
                "가장 맛있는 시기를 놓치지 않는 것이 중요합니다."
            )

        elif "장어" in search:
            body = (
                "장어는 원물 상태가 좋을 때\n"
                "구웠을 때의 식감과 풍미가 가장 살아납니다.\n\n"
                "신선한 상태에서 준비한 장어의 차이를 느껴보세요."
            )

        elif any(
            word in search
            for word in ["굴", "전복", "소라", "조개", "고동"]
        ):
            body = (
                "패류는 계절과 해역의 영향을 많이 받습니다.\n\n"
                "좋은 시기에 채취한 원물은\n"
                "식감과 자연스러운 단맛이 더욱 뛰어납니다."
            )

        elif any(
            word in search
            for word in ["오징어", "갑오징어", "문어", "낙지"]
        ):
            body = (
                "두족류는 신선도가 맛을 결정합니다.\n\n"
                "좋은 상태에서 준비한 원물은\n"
                "탄력과 풍미가 확연히 다릅니다."
            )

        elif any(
            word in search
            for word in ["멸치", "방어", "전어", "생선", "참치"]
        ):
            body = (
                "생선은 시간이 지날수록 맛과 식감이 달라집니다.\n\n"
                "신선도가 가장 좋을 때 준비한 상품은\n"
                "비린 맛은 줄고 감칠맛은 더욱 살아납니다."
            )

        elif any(
            word in search
            for word in ["복숭아", "사과", "배", "포도", "과일"]
        ):
            body = (
                "과일은 수확 시기를 놓치면\n"
                "맛과 향의 균형이 달라집니다.\n\n"
                "가장 맛있는 시기에 즐기는 것이 가장 큰 차이입니다."
            )

        else:
            body = (
                "좋은 상품은 항상 같은 상태로 준비되지 않습니다.\n\n"
                "원물의 상태가 가장 좋을 때 선별해 준비한\n"
                "지금의 품질을 만나보세요."
            )

        return (
            f"왜 지금 {name}을 추천할까요?",
            body,
        )

    def write_usp(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)
        key_point = self.value(
            product,
            "key_point",
            "상태와 품질 기준을 확인해 선별했습니다.",
        )

        usp = str(
            playbook.get("usp")
            or f"{name}의 차이는 선별에서 시작됩니다."
        ).strip()

        return usp, key_point

    def write_origin(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)
        category = self.value(product, "category")
        origin = self.value(product, "origin", "좋은 산지")
        story = self.value(product, "production_story")
        shipping = self.value(product, "shipping_text")
        dna = self.value(product, "product_dna")

        search = f"{name} {category} {origin} {dna}".lower()

        if story:
            return (
                f"{name}, {origin}에서 준비합니다",
                story,
            )

        if any(word in search for word in ["홍게", "대게", "꽃게"]):
            body = (
                f"{origin}에서 조업한 {name}을 준비합니다.\n\n"
                "게류는 조업 시기와 선도, 보관 상태에 따라\n"
                "살의 수율과 맛의 차이가 크게 달라집니다.\n\n"
                "입고된 원물의 상태를 확인한 뒤\n"
                "판매 기준에 맞는 상품만 선별해 출고합니다."
            )

        elif any(
            word in search
            for word in ["굴", "전복", "소라", "조개", "고동"]
        ):
            body = (
                f"{origin}의 바다에서 채취한 {name}입니다.\n\n"
                "패류는 자라는 해역과 채취 환경에 따라\n"
                "살의 크기와 식감, 풍미가 달라집니다.\n\n"
                "채취 후 원물 상태를 확인하고\n"
                "신선함이 유지될 수 있도록 준비합니다."
            )

        elif any(
            word in search
            for word in ["오징어", "갑오징어", "문어", "낙지"]
        ):
            body = (
                f"{origin}에서 조업한 {name}을 준비합니다.\n\n"
                "조업 후 시간이 길어질수록\n"
                "탄력과 색, 원물의 풍미가 빠르게 달라집니다.\n\n"
                "입고 시 선도와 표면 상태를 확인하고\n"
                "상품 특성에 맞춰 신속하게 출고합니다."
            )

        elif any(
            word in search
            for word in ["멸치", "방어", "전어", "생선", "참치"]
        ):
            body = (
                f"{origin}에서 잡아 올린 {name}입니다.\n\n"
                "생선은 산지뿐 아니라\n"
                "조업 후 얼마나 빠르게 관리되는지가 중요합니다.\n\n"
                "원물의 색과 탄력, 선도를 확인한 뒤\n"
                "먹는 방식에 적합한 상태로 준비합니다."
            )

        elif "장어" in search:
            body = (
                f"{origin}에서 관리한 {name}을 준비합니다.\n\n"
                "장어는 사육 환경과 출하 전 관리에 따라\n"
                "살집과 지방의 균형, 식감이 달라집니다.\n\n"
                "원물 상태와 크기를 확인한 뒤\n"
                "손질과 조리에 적합한 상품을 선별합니다."
            )

        elif any(
            word in search
            for word in ["복숭아", "사과", "배", "포도", "과일"]
        ):
            body = (
                f"{origin}에서 자란 {name}입니다.\n\n"
                "과일은 같은 산지에서도\n"
                "수확 시기와 숙도에 따라 맛의 차이가 생깁니다.\n\n"
                "향과 과육 상태, 숙도를 확인한 뒤\n"
                "먹기 좋은 상품을 선별해 준비합니다."
            )

        else:
            body = (
                f"{origin}에서 준비한 {name}입니다.\n\n"
                "좋은 상품은 산지 이름만으로 결정되지 않습니다.\n"
                "생산과 입고 과정, 원물의 실제 상태를 함께 확인합니다.\n\n"
                "비선상회 기준에 맞는 상품만 선별해 소개합니다."
            )

        if shipping:
            body = f"{body}\n\n{shipping}"

        return (
            f"{name}의 시작은 {origin}입니다",
            body,
        )

    def write_selection(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)
        key_point = self.value(product, "key_point")

        if key_point:
            return (
                f"{name}, 이렇게 선별합니다",
                key_point,
            )

        knowledge = self.get_knowledge(product)

        if knowledge:
            selection = list(knowledge.get("selection", []))
            selling = list(knowledge.get("selling_point", []))

            selected_selection = random.sample(
                selection,
                k=min(2, len(selection)),
            )

            selected_selling = random.sample(
                selling,
                k=min(1, len(selling)),
            )

            return (
                "이렇게 선별했습니다",
                (
                    f"{selected_selection[0]}\n\n"
                    f"{selected_selection[1] if len(selected_selection) > 1 else ''}\n\n"
                    f"{selected_selling[0] if selected_selling else '비선상회 기준으로 선별한 상품만 소개합니다.'}"
                ),
            )

        return (
            f"좋은 {name}은 선별부터 다릅니다",
            (
                f"모든 {name}을 같은 상품으로 보지 않습니다.\n\n"
                "크기와 외형뿐 아니라 상태와 신선도,\n"
                "실제로 먹었을 때의 만족도를 기준으로 선별합니다."
            ),
        )

    def write_taste(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        taste = self.value(product, "taste_texture")

        if taste:
            return (
                "한입에서 느껴지는 맛의 차이",
                taste,
            )

        knowledge = self.get_knowledge(product)
        tastes = list((knowledge or {}).get("taste", []))

        if tastes:
            selected = random.sample(
                tastes,
                k=min(2, len(tastes)),
            )

            return (
                "한입에서 느껴지는 차이",
                "\n".join(selected),
            )

        return (
            "한입에서 느껴지는 차이",
            (
                "원물 본연의 맛과 식감을 가장 잘 느낄 수 있도록\n"
                "좋은 상태의 상품을 준비했습니다."
            ),
        )

    def write_how_to(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        usage = self.value(product, "usage_text")

        if usage:
            return (
                "이렇게 드시면 더 맛있습니다",
                usage,
            )

        knowledge = self.get_knowledge(product)
        recommendations = list(
            (knowledge or {}).get("recommended", [])
        )

        if recommendations:
            selected = random.sample(
                recommendations,
                k=min(2, len(recommendations)),
            )

            return (
                "이렇게 드시면 더 맛있습니다",
                "\n\n".join(selected),
            )

        return (
            "이렇게 드시면 더 맛있습니다",
            (
                "재료 본연의 맛을 먼저 즐긴 뒤\n"
                "상품에 어울리는 다양한 조리법으로 활용해 보세요."
            ),
        )
    def write_prep(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        prep = self.value(
            product,
            "prep_text",
            self.value(
                product,
                "usage_text",
                (
                    "수령한 상품의 상태를 먼저 확인하고\n"
                    "상품 특성에 맞춰 세척하거나 해동한 뒤 조리해 주세요."
                ),
            ),
        )

        return (
            "손질과 조리, 어렵지 않게",
            prep,
        )

    def write_option(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:

        name = (
            product.get("display_name")
            or product.get("product_name")
            or "상품"
        )

        option_name = product.get("option_name", "")

        option_text = self.value(
            product,
            "option_text",
            (
                "상품별 중량과 구성 수량이 다를 수 있습니다.\n"
                "구매 전 선택한 옵션을 꼭 확인해 주세요."
            ),
        )

        body = f"""{name}

    옵션 : {option_name}

    {option_text}""".strip()

        return (
            "구성과 옵션을 확인해 주세요",
            body,
        )
    def write_packing(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        shipping = self.value(
            product,
            "shipping_text",
            (
                "상품 특성에 맞는 포장재를 사용해 준비합니다.\n"
                "산지와 출고 일정에 따라 가장 안전한 상태로 발송합니다."
            ),
        )

        return (
            "좋은 상태가 도착할 때까지",
            shipping,
        )

    def write_notice(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        storage = self.value(
            product,
            "storage_text",
            "수령 즉시 상품 상태를 확인하고 냉장 또는 냉동 보관해 주세요.",
        )

        caution = self.value(
            product,
            "caution_text",
            (
                "신선식품은 자연물 특성상\n"
                "모양과 색상, 크기와 중량에 차이가 있을 수 있습니다."
            ),
        )

        return (
            "구매 전 꼭 확인해 주세요",
            f"{storage}\n\n{caution}",
        )

    def write_cs(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        brand = product.get("brand") or {}

        phone = str(
            brand.get("customer_phone")
            or "고객센터 전화번호 입력"
        ).strip()

        hours = str(
            brand.get("customer_hours")
            or "평일 상담 가능 시간 입력"
        ).strip()

        cs_policy = str(
            brand.get("cs_policy")
            or (
                "상품에 이상이 있다면 수령 즉시\n"
                "상품 전체와 송장 사진을 준비해 문의해 주세요."
            )
        ).strip()

        return (
            "문제가 있다면 바로 말씀해 주세요",
            f"고객센터 {phone}\n{hours}\n\n{cs_policy}",
        )

    def write_quality(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        brand = product.get("brand") or {}

        quality = str(
            brand.get("quality_text")
            or (
                "전국 산지 엄선\n"
                "상태를 확인한 상품만 소개\n"
                "품질에 맞는 합리적인 가격\n"
                "상품에 맞는 안전한 포장"
            )
        ).strip()

        slogan = str(
            brand.get("slogan")
            or "처음은 상품 때문에, 다음은 비선상회 때문에."
        ).strip()

        return (
            "비선상회 품질 기준",
            f"{quality}\n\n{slogan}",
        )

    def write_cta(
        self,
        product: dict[str, Any],
        playbook: dict[str, Any],
    ) -> tuple[str, str]:
        name = self.product_name(product)
        category = self.value(product, "category")
        dna = self.value(product, "product_dna")
        custom_cta = self.value(product, "cta_text")

        search = f"{name} {category} {dna}".lower()

        if custom_cta:
            return (
                "지금 만나보세요",
                custom_cta,
            )

        if any(word in search for word in ["홍게", "대게"]):
            title = "살이 꽉 찬 게를 찾고 계셨다면"
            body = (
                "좋은 원물이 들어왔을 때 준비한 상품입니다.\n"
                "오늘 식탁에서 제대로 된 게의 맛을 즐겨보세요."
            )

        elif "꽃게" in search:
            title = "제철 꽃게의 풍미를 즐길 시간입니다"
            body = (
                "살과 알의 상태를 꼼꼼히 확인해 선별했습니다.\n"
                "가장 맛있는 시기의 꽃게를 만나보세요."
            )

        elif "장어" in search:
            title = "오늘은 제대로 된 장어 한 끼"
            body = (
                "굵기와 식감까지 고려해 준비한 장어입니다.\n"
                "집에서도 전문점 같은 풍미를 경험해 보세요."
            )

        elif any(
            word in search
            for word in ["굴", "전복", "소라", "조개", "고동"]
        ):
            title = "바다의 신선함을 그대로"
            body = (
                "신선도가 가장 중요한 상품인 만큼\n"
                "좋은 상태로 준비해 보내드립니다."
            )

        elif any(
            word in search
            for word in ["오징어", "갑오징어", "문어", "낙지"]
        ):
            title = "쫄깃한 식감의 차이를 느껴보세요"
            body = (
                "원물의 선도를 우선으로 준비했습니다.\n"
                "씹을수록 살아나는 풍미를 경험해 보세요."
            )

        elif any(
            word in search
            for word in ["멸치", "방어", "전어", "생선", "참치"]
        ):
            title = "신선할 때 가장 맛있습니다"
            body = (
                "좋은 생선은 신선도가 중요합니다.\n"
                "가장 맛있는 상태로 준비해 보내드립니다."
            )

        elif any(
            word in search
            for word in ["복숭아", "사과", "배", "포도", "과일"]
        ):
            title = "가장 맛있는 순간을 담았습니다"
            body = (
                "먹기 좋은 시기에 선별한 과일입니다.\n"
                "계절이 주는 자연의 맛을 즐겨보세요."
            )

        else:
            playbook_cta = str(
                playbook.get("cta")
                or f"좋은 {name}, 이제 경험해 보세요."
            ).strip()

            title = playbook_cta
            body = (
                "비선상회는 상품보다 먼저 품질을 생각합니다.\n"
                "믿고 다시 찾을 수 있는 상품을 보내드리겠습니다."
            )

        return title, body
    
    def apply_brand_voice(
        self,
        title: str,
        body: str,
    ) -> tuple[str, str]:

        voice = self.get_voice()

        for word in voice["avoid_words"]:
            body = body.replace(word, "")

        body = body.replace("최고의", "좋은")
        body = body.replace("최상", "좋은")
        body = body.replace("무조건", "")
        body = body.replace("100%", "")
        body = body.replace("역대급", "")

        return title.strip(), body.strip()