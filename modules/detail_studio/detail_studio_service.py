from __future__ import annotations
from .reviewer import DetailReviewer
from .product_name_parser import parse_product_name
from .product_classifier import classify_product
import base64
import html
import json
import mimetypes
import sqlite3
from .playbook_engine import PlaybookEngine
from .section_writer import SectionWriter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"

DEFAULT_BRAND = {
    "brand_name": "비선상회",
    "slogan": "처음은 상품 때문에, 다음은 비선상회 때문에.",
    "intro_text": "좋은 농수산물은 많습니다. 하지만 아무거나 소개하지는 않습니다.",
    "quality_text": "전국 산지 엄선\n직접 확인한 상품만 소개\n품질에 맞는 합리적인 가격\n상품에 맞는 안전한 포장\n다시 찾을 수 있는 상품",
    "customer_phone": "",
    "customer_hours": "평일 상담 가능 시간 입력",
    "shipping_policy": "상품별 출고 마감과 택배 일정은 상세 안내를 확인해 주세요.",
    "cs_policy": "수령 즉시 상품 상태를 확인해 주세요. 이상이 있다면 상품과 송장 사진을 준비해 고객센터로 문의해 주세요.",
}

SECTION_SPECS = [
    ("brand_intro", "브랜드 인트로", "brand", 1, "브랜드/상품 대표 이미지"),
    ("hero", "상품 메인 훅", "main", 3, "메인 컷"),
    ("why_now", "지금 먹어야 하는 이유", "food", 2, "제철/완성 음식"),
    ("usp", "핵심 차별점", "main", 2, "원물 접사/비교"),
    ("origin", "산지·생산 이야기", "origin", 3, "산지/조업/수확"),
    ("selection", "선별·품질 기준", "main", 2, "선별 상태/크기"),
    ("taste", "맛과 식감", "food", 3, "완성컷/젓가락 접사"),
    ("how_to", "맛있게 먹는 방법", "food", 3, "조리/상차림"),
    ("prep", "손질·조리 방법", "prep", 4, "손질 전/과정/완료"),
    ("option", "구성·옵션", "option", 3, "구성품/중량"),
    ("packing", "포장·배송", "packing", 3, "내부 포장/박스"),
    ("notice", "수령·보관·주의사항", "notice", 1, "안내 그래픽"),
    ("cs", "고객센터·CS", "brand", 1, "CS 공통 이미지"),
    ("quality", "비선상회 품질 기준", "brand", 1, "상품 맞춤 브랜드 엔딩"),
    ("cta", "최종 구매 유도", "food", 1, "최종 완성컷"),
]


class DetailStudioService:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or DATABASE_PATH
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self.playbook = PlaybookEngine()
        self.section_writer = SectionWriter()
        self.reviewer = DetailReviewer()

        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS detail_brand_settings (
                id INTEGER PRIMARY KEY CHECK(id=1), settings_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS detail_page_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, project_name TEXT NOT NULL,
                product_name TEXT NOT NULL, project_json TEXT NOT NULL, generated_copy TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS detail_page_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, section_key TEXT NOT NULL,
                slot_no INTEGER NOT NULL, file_path TEXT, source_type TEXT DEFAULT 'upload', ai_prompt TEXT,
                status TEXT DEFAULT 'empty', created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS detail_copy_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT, copy_type TEXT NOT NULL, copy_text TEXT NOT NULL,
                product_name TEXT, rating INTEGER DEFAULT 5, is_favorite INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            row = conn.execute("SELECT id FROM detail_brand_settings WHERE id=1").fetchone()
            if not row:
                conn.execute("INSERT INTO detail_brand_settings(id,settings_json) VALUES(1,?)", (json.dumps(DEFAULT_BRAND, ensure_ascii=False),))
            conn.commit()

    def get_products(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT id, product_name, option_name, sale_price, platform_product_name FROM products WHERE COALESCE(is_active,1)=1 ORDER BY product_name, option_name").fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    def get_brand(self) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute("SELECT settings_json FROM detail_brand_settings WHERE id=1").fetchone()
        saved = json.loads(row[0]) if row else {}
        return {**DEFAULT_BRAND, **saved}

    def save_brand(self, data: dict[str, str]) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE detail_brand_settings SET settings_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(data, ensure_ascii=False),))
            conn.commit()

    @staticmethod
    def section_specs() -> list[tuple]:
        return SECTION_SPECS

    def build_sections(self, data: dict[str, Any]) -> list[dict[str, Any]]:

        name_info = parse_product_name(
            data.get("product_name", "")
        )

        data["display_name"] = name_info["display_name"]
        data["option_name"] = name_info["option_name"]

        classification = classify_product(data)

        if not data.get("category"):
            data["category"] = classification["category"]

        if not data.get("origin"):
            data["origin"] = classification["origin"]

        if not data.get("grade"):
            data["grade"] = classification["grade"]

        playbook = self.playbook.build(
            product=data,
            interview=data.get("interview_answers", {}),
            brand=data.get("brand", {}),
        )

        p=lambda k,d="": str(data.get(k) or d).strip()
        product=p("display_name", p("product_name", "상품"))
        origin=p("origin","좋은 산지")
        key=p("key_point","상태와 선별 기준을 먼저 확인했습니다.")
        taste=p("taste_texture","재료 본연의 맛과 식감을 즐길 수 있습니다.")
        usage=p("usage_text","상품에 맞는 가장 맛있는 방법으로 즐겨보세요.")
        story=p("production_story",f"{origin}에서 준비한 {product}입니다.")
        option=p("option_text","판매 옵션을 확인해 주세요.")
        shipping=p("shipping_text","상품 특성에 맞춰 포장해 출고합니다.")
        storage=p("storage_text","수령 즉시 확인 후 상품 특성에 맞게 보관해 주세요.")
        caution=p("caution_text","신선식품은 모양과 중량에 자연스러운 차이가 있을 수 있습니다.")
        brand={**self.get_brand(), **(data.get("brand") or {})}
        dna=[x.strip() for x in p("product_dna").replace("/",",").split(",") if x.strip()]
        dna_text=" · ".join(dna[:4]) or "신선함 · 제철 · 좋은 한 끼"
        hook_candidates=[
            f"지금 가장 맛있을 때, {product}",
            f"한 입에서 느껴지는 {dna[0] if dna else '제철의 차이'}",
            f"좋은 {product}은 첫입부터 다릅니다.",
            f"오늘 식탁이 기다리던 {product}",
            f"{origin}에서 찾은, 제대로 된 {product}",
        ]
        hook = p("selected_hook", playbook["hook"])
        objections=p("customer_worries","상태가 괜찮을까?\n배송 중 문제가 생기지 않을까?\n사진과 실제 상품이 다르지 않을까?")
        sections = {}

        for section_key, *_ in SECTION_SPECS:
            title, body = self.section_writer.write(
                section=section_key,
                product={
                    **data,
                    "brand": brand,
                },
                playbook=playbook,
            )

            title, body, score = self.reviewer.review_section(
                title=title,
                body=body,
                product=data,
            )

            sections[section_key] = {
                "title": title,
                "body": body,
                "score": score,
            }
        enabled=set(data.get("enabled_sections") or sections.keys())
        result=[]
        order = playbook["section_priority"]

        specs = sorted(
            SECTION_SPECS,
            key=lambda x: order.index(x[0]) if x[0] in order else 999
        )

        for key, label, group, count, desc in specs:
            if key not in enabled: continue
            section = sections[key]

            title = section["title"]
            body = section["body"]
            score = section["score"]
            assets = (data.get("assets") or {}).get(key, [])
            result.append({"key":key,"label":label,"group":group,"title":title,"body":body,"asset_count":count,"asset_desc":desc,"assets":assets,"score": score,})
        return result

    def hooks(self, data: dict[str, Any]) -> list[str]:
        product=str(data.get("product_name") or "상품")
        origin=str(data.get("origin") or "산지")
        dna=[x.strip() for x in str(data.get("product_dna") or "").replace("/",",").split(",") if x.strip()]
        d=dna or ["신선함","제철","풍미"]
        return [
            f"지금 가장 맛있을 때, {product}", f"좋은 {product}은 첫입부터 다릅니다.",
            f"{origin}에서 찾은, 제대로 된 {product}", f"한 입에서 느껴지는 {d[0]}의 차이",
            f"오늘 식탁이 기다리던 {product}", f"마트에서는 만나기 어려운 {product}",
            f"복잡한 준비 없이, 맛있는 {product}", f"사진보다 실제 한입이 더 좋은 {product}",
            f"제철은 기다려주지 않습니다. {product}", f"처음은 {product} 때문에, 다음은 비선상회 때문에.",
        ]

    def ai_prompt(self, data: dict[str, Any], section_key: str, slot_no: int) -> str:
        spec=next((s for s in SECTION_SPECS if s[0]==section_key), None)
        label=spec[1] if spec else section_key
        desc=spec[4] if spec else "상품 이미지"
        product=data.get("product_name") or "상품"
        origin=data.get("origin") or "한국"
        return (f"{product} 상세페이지의 '{label}' 섹션용 {desc} 사진. {origin}과 한국 식문화에 자연스럽게 맞는 실제 촬영 사진 느낌, "
                "스마트폰 또는 미러리스로 촬영한 듯 자연스러운 빛, 과도한 광택과 과포화 금지, 상품 크기와 형태 왜곡 금지, "
                "완벽하게 정렬된 광고 사진보다 현실적인 식탁과 작업 흔적, 텍스트·로고·워터마크 없음. "
                f"슬롯 {slot_no}. 실제 산지·실제 포장·실제 구성 증명이 필요한 장면이라면 AI 생성 대신 실제 사진 사용 안내.")

    def interview_questions(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        product=str(data.get("product_name") or "상품").strip()
        category=str(data.get("category") or "").strip().lower()
        name=(product+" "+category).lower()
        questions=[
            {"key":"main_sales_axis","question":"이 상품은 무엇으로 가장 강하게 팔까요?","type":"choice","choices":["맛·식감","가격·가성비","희소성","제철성","선물·고급감"]},
            {"key":"why_selected","question":"대표님이 이 상품을 가져온 가장 큰 이유는 무엇인가요?","type":"text"},
            {"key":"customer_question","question":"고객이 가장 많이 묻거나 걱정할 내용은 무엇인가요?","type":"text"},
            {"key":"must_emphasize","question":"상세페이지에서 절대 빠지면 안 되는 사실은 무엇인가요?","type":"text"},
            {"key":"target_customer","question":"가장 먼저 사고 싶게 만들어야 할 고객은 누구인가요?","type":"text"},
        ]
        if "꽃게" in name:
            questions += [
                {
                    "key": "crab_gender",
                    "question": "암꽃게·수꽃게 중 어떤 상품인가요?",
                    "type": "choice",
                    "choices": ["암꽃게", "수꽃게", "혼합", "확인 필요"],
                },
                {
                    "key": "roe_status",
                    "question": "알배기 여부와 알 선별 기준은 어떻게 되나요?",
                    "type": "text",
                },
                {
                    "key": "live_condition",
                    "question": "활·생물·냉동 중 어떤 상태로 출고되며 활 상태는 어떻게 관리하나요?",
                    "type": "text",
                },
                {
                    "key": "catch_origin",
                    "question": "주요 조업지와 조업·입고·출고 흐름은 어떻게 되나요?",
                    "type": "text",
                },
            ]

        elif any(x in name for x in ["홍게", "대게"]):
            questions += [
                {
                    "key": "yield_info",
                    "question": "다리와 몸통 수율은 각각 어느 정도인가요? 모르면 '확인 필요'라고 적어주세요.",
                    "type": "text",
                },
                {
                    "key": "processing_state",
                    "question": "활·생물·자숙·냉동 중 어떤 상태로 출고되나요?",
                    "type": "text",
                },
                {
                    "key": "crab_size",
                    "question": "마리당 크기·중량·구성 수량은 어떻게 되나요?",
                    "type": "text",
                },
                {
                    "key": "cooking_process",
                    "question": "자숙 상품이라면 자숙·냉각·포장 과정은 어떻게 진행되나요?",
                    "type": "text",
                },
            ]
        elif any(x in name for x in ["복숭아","사과","배","포도","과일"]):
            questions += [
                {"key":"sweetness_info","question":"당도 수치 또는 맛의 특징을 증명할 수 있는 정보가 있나요?","type":"text"},
                {"key":"selection_grade","question":"크기·흠과·선물용 등 선별 기준은 어떻게 되나요?","type":"text"},
            ]
        elif "장어" in name:
            questions += [
                {
                    "key": "eel_species",
                    "question": "장어 품종과 원산지는 무엇인가요?",
                    "type": "text",
                },
                {
                    "key": "trim_weight",
                    "question": "손질 전후 중량과 손질 방식은 어떻게 되나요?",
                    "type": "text",
                },
                {
                    "key": "pre_cooked",
                    "question": "생물·손질·초벌 중 어떤 상태로 출고되나요?",
                    "type": "choice",
                    "choices": ["생물", "손질", "초벌", "기타"],
                },
                {
                    "key": "cooking_tip",
                    "question": "가장 실패 없이 굽는 방법과 권장 조리 시간은 무엇인가요?",
                    "type": "text",
                },
            ]
        elif any(x in name for x in ["고동","소라","굴","전복","조개","패류"]):
            questions += [
                {"key":"wild_farmed","question":"자연산인가요, 양식인가요? 채취·조업 방식도 알려주세요.","type":"text"},
                {"key":"prep_warning","question":"해감·세척·삶는 시간 등 꼭 필요한 손질 안내는 무엇인가요?","type":"text"},
            ]
        elif any(x in name for x in ["오징어","멸치","방어","참치","생선","수산"]):
            questions += [
                {"key":"catch_ship","question":"조업·입고·출고 흐름과 신선도를 설명할 수 있나요?","type":"text"},
                {"key":"best_use","question":"회·숙회·구이 등 가장 추천하는 섭취 방법은 무엇인가요?","type":"text"},
            ]
        questions += [
            {"key":"real_photo_status","question":"실제 상품·포장·산지 사진은 각각 준비되어 있나요?","type":"text"},
            {"key":"fact_warning","question":"과장 없이 반드시 고지해야 할 제한·편차·주의사항은 무엇인가요?","type":"text"},
        ]
        return questions

    def apply_interview_answers(
        self,
        data: dict[str, Any],
        answers: dict[str, str],
    ) -> dict[str, Any]:
        out = dict(data)

        mappings = {
            "main_sales_axis": "sales_axis",
            "why_selected": "production_story",
            "customer_question": "customer_worries",
            "must_emphasize": "key_point",
            "target_customer": "target_customer",

            "yield_info": "key_point",
            "roe_status": "key_point",
            "catch_origin": "origin",
            "processing_state": "production_story",
            "live_condition": "production_story",
            "crab_size": "option_text",
            "cooking_process": "production_story",

            "trim_weight": "option_text",
            "eel_species": "origin",
            "pre_cooked": "production_story",
            "cooking_tip": "prep_text",

            "sweetness_info": "taste_texture",
            "selection_grade": "key_point",

            "wild_farmed": "production_story",
            "prep_warning": "prep_text",

            "catch_ship": "production_story",
            "best_use": "usage_text",

            "fact_warning": "caution_text",
            "real_photo_status": "key_point",
        }

        interview_answers = dict(out.get("interview_answers") or {})

        for key, value in answers.items():
            value = str(value or "").strip()

            if not value:
                continue

            interview_answers[key] = value
            target = mappings.get(key)

            if not target:
                continue

            current = str(out.get(target) or "").strip()

            if not current:
                out[target] = value
            elif value not in current:
                out[target] = f"{current}\n{value}"

        out["interview_answers"] = interview_answers

        return out

    def strategy_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        product=str(data.get("product_name") or "상품")
        axis=str(data.get("sales_axis") or data.get("main_sales_axis") or "").strip()
        if not axis:
            dna=str(data.get("product_dna") or "")
            axis="희소성 중심" if any(x in dna for x in ["희소","자연산","제철"]) else "품질·신뢰 중심"
        strengths=[]
        for label,key in [("핵심 차별점","key_point"),("제철·타이밍","why_now"),("맛·식감","taste_texture"),("산지·생산","production_story")]:
            if str(data.get(key) or "").strip(): strengths.append(label)
        missing=self.missing_check(data)
        return {
            "product":product,"axis":axis,"strengths":strengths or ["기본 상품 정보"],
            "target":str(data.get("target_customer") or "핵심 구매 고객 입력 필요"),
            "risk_count":len(missing),"missing":missing,
            "recommendation":f"{axis}으로 첫 화면을 구성하고, 실제 사진과 구체적인 선별 근거를 앞부분에 배치하세요.",
        }

    def md_analysis(self, data: dict[str, Any]) -> dict[str, Any]:
        score = 100
        tips = []

        if not str(data.get("product_name") or "").strip():
            score -= 20
            tips.append("상품명을 입력하세요.")

        if not str(data.get("origin") or "").strip():
            score -= 10
            tips.append("원산지를 입력하세요.")

        if not str(data.get("key_point") or "").strip():
            score -= 10
            tips.append("핵심 장점을 보강하세요.")

        if not str(data.get("taste_texture") or "").strip():
            score -= 10
            tips.append("맛과 식감 설명을 추가하세요.")

        if not str(data.get("prep_text") or "").strip():
            score -= 5
            tips.append("조리 방법을 추가하세요.")

        if not str(data.get("shipping_text") or "").strip():
            score -= 5
            tips.append("배송 안내를 추가하세요.")

        if not str(data.get("cta_text") or "").strip():
            score -= 5
            tips.append("CTA를 작성하세요.")

        strategy = "품질·신뢰 중심"

        dna = str(data.get("product_dna") or "")

        if "자연산" in dna:
            strategy = "희소성 중심"

        if "제철" in dna:
            strategy = "제철성 중심"

        if "당일" in dna:
            strategy = "신선도 중심"

        return {
        "score": max(score, 0),
        "strategy": strategy,
        "tips": tips
    }

    def missing_check(self, data: dict[str, Any]) -> list[str]:
        checks=[
            ("product_name","상품명"),("origin","원산지·산지"),("key_point","핵심 장점·선별 기준"),
            ("customer_worries","고객 구매 불안"),("taste_texture","맛·식감"),("usage_text","먹는 방법"),
            ("shipping_text","출고·배송 안내"),("storage_text","보관 방법"),("caution_text","주의사항"),
        ]
        missing=[f"{label} 입력 필요" for key,label in checks if not str(data.get(key) or "").strip()]
        audit=self.image_audit(data.get("assets") or {})
        for tip in audit.get("tips",[]):
            if "충분" not in tip: missing.append(tip)
        return missing

    def save_project(self, data: dict[str, Any], generated_copy: str) -> int:
        payload=json.dumps(data, ensure_ascii=False)
        with self._connect() as conn:
            cur=conn.execute("INSERT INTO detail_page_projects(product_id,project_name,product_name,project_json,generated_copy,updated_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                (data.get("product_id"),data.get("project_name") or data.get("product_name"),data.get("product_name"),payload,generated_copy))
            pid=int(cur.lastrowid)
            for section,items in (data.get("assets") or {}).items():
                for i,item in enumerate(items,1):
                    conn.execute("INSERT INTO detail_page_assets(project_id,section_key,slot_no,file_path,source_type,ai_prompt,status) VALUES(?,?,?,?,?,?,?)",
                        (pid,section,i,item.get("path"),item.get("source","upload"),item.get("prompt"),item.get("status","ready")))
            conn.commit(); return pid


    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, project_name, product_name, created_at, updated_at FROM detail_page_projects ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def load_project(self, project_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT project_json, generated_copy FROM detail_page_projects WHERE id=?", (project_id,)
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        data["generated_copy"] = row[1] or ""
        return data

    def save_copy(self, copy_type: str, copy_text: str, product_name: str = "", rating: int = 5) -> int:
        text = (copy_text or "").strip()
        if not text:
            raise ValueError("저장할 카피가 없습니다.")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO detail_copy_library(copy_type,copy_text,product_name,rating,is_favorite) VALUES(?,?,?,?,1)",
                (copy_type, text, product_name, max(1, min(5, int(rating)))),
            )
            conn.commit()
            return int(cur.lastrowid)

    def favorite_copies(self, copy_type: str = "", limit: int = 30) -> list[dict[str, Any]]:
        query = "SELECT * FROM detail_copy_library"
        params: list[Any] = []
        if copy_type:
            query += " WHERE copy_type=?"
            params.append(copy_type)
        query += " ORDER BY rating DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def sales_score(self, data: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        text = " ".join([str(data.get(k) or "") for k in (
            "product_dna", "key_point", "customer_worries", "why_now", "production_story",
            "taste_texture", "usage_text", "shipping_text", "cta_text"
        )])
        assets = [a for items in (data.get("assets") or {}).values() for a in items if a.get("status") == "ready"]
        hook = 55 + min(35, len(str(data.get("selected_hook") or "")) * 2)
        trust = 45 + (15 if data.get("origin") else 0) + (15 if data.get("production_story") else 0) + (15 if data.get("key_point") else 0)
        objection = 40 + (35 if data.get("customer_worries") else 0) + (15 if data.get("shipping_text") else 0)
        visual = min(100, 35 + len(assets) * 9)
        readability = 92 if len(sections) <= 15 else 82
        brand = 60 + (20 if any(s.get("key") == "quality" for s in sections) else 0) + (15 if any(s.get("key") == "brand_intro" for s in sections) else 0)
        cta = 55 + (35 if len(str(data.get("cta_text") or "")) >= 10 else 10)
        scores = {
            "후킹": min(100, hook), "신뢰도": min(100, trust), "구매불안 해소": min(100, objection),
            "사진": visual, "가독성": readability, "브랜드": min(100, brand), "CTA": min(100, cta),
        }
        total = round(sum(scores.values()) / len(scores))
        tips=[]
        if visual < 80: tips.append(f"실제 상품·조리·포장 사진을 {max(1, (80-visual+8)//9)}장 추가하면 신뢰도가 올라갑니다.")
        if trust < 80: tips.append("산지와 선별 기준을 구체적인 사실 중심으로 보강하세요.")
        if objection < 80: tips.append("고객이 망설이는 이유와 배송·수령 대응을 첫 화면 가까이에 배치하세요.")
        if cta < 80: tips.append("마지막 CTA에 지금 구매해야 하는 이유를 한 문장으로 넣으세요.")
        if not tips: tips.append("판매에 필요한 핵심 정보가 균형 있게 구성되었습니다. 실제 업로드 후 반응을 기록하세요.")
        return {"total": total, "scores": scores, "tips": tips}

    def content_package(self, data: dict[str, Any], sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        product = str(data.get("product_name") or "상품").strip()
        origin = str(data.get("origin") or "산지").strip()
        category = str(data.get("category") or "신선식품").strip()
        dna = [x.strip() for x in str(data.get("product_dna") or "").replace("/", ",").split(",") if x.strip()]
        key = str(data.get("key_point") or "상태와 선별 기준을 확인한 상품").strip()
        taste = str(data.get("taste_texture") or "재료 본연의 맛과 식감").strip()
        usage = str(data.get("usage_text") or "간단하게 준비해 맛있게 즐겨보세요.").strip()
        why = str(data.get("why_now") or "좋은 시기와 좋은 상태가 만났을 때 가장 만족스럽습니다.").strip()
        option = str(data.get("option_text") or "옵션 확인").strip()
        hook = str(data.get("selected_hook") or self.hooks(data)[0]).strip()
        d1 = dna[0] if dna else "제철의 맛"
        d2 = dna[1] if len(dna) > 1 else "신선함"

        product_names = [
            f"[{origin}] {product} {option}",
            f"비선상회 {origin} {product} {option}",
            f"{d1} 좋은 {product} 산지직송 {option}",
            f"{product} {option} {d1} {d2}",
            f"오늘의 제철 {origin} {product} {option}",
        ]
        seo: list[str] = []
        seeds = [product, origin, category, option, d1, d2, "산지직송", "제철", "신선식품", "비선상회", "집들이음식", "술안주", "캠핑음식", "간편조리", "선물"]
        for item in seeds:
            item = item.strip()
            if item and item not in seo:
                seo.append(item)
        extras = [f"{origin}{product}", f"{product}먹는법", f"{product}손질법", f"{product}보관법", f"{product}요리", f"{product}택배", f"{product}산지직송", f"{product}제철", f"{product}추천", f"{product}구매"]
        for item in extras:
            if item not in seo:
                seo.append(item)

        shorts = "\n".join([
            hook, "", "마트에서 흔히 보던 상품과는 다릅니다.", f"{origin}에서 준비한 {product}.", "",
            key, "", f"한입에서는 {taste}", usage, "", why, "", "처음은 상품 때문에,", "다음은 비선상회 때문에."
        ])
        blog = "\n".join([
            f"제목: {origin} {product}, 지금 먹어야 하는 이유와 맛있게 먹는 법", "",
            f"{product}을 고를 때 가장 먼저 확인해야 할 것은 가격보다 상태와 선별 기준입니다. 비선상회는 {origin}에서 준비되는 상품 가운데 {key}", "",
            f"■ 왜 지금 {product}인가요?", why, "", "■ 맛과 식감", taste, "", "■ 맛있게 먹는 방법", usage, "",
            "■ 구성과 옵션", option, "",
            "신선식품은 자연물 특성상 모양과 중량에 차이가 있을 수 있습니다. 수령 즉시 상태를 확인하고 상품 특성에 맞게 보관해 주세요. 좋은 상품을 누구나 합리적으로 누릴 수 있도록, 비선상회는 판매보다 선별을 먼저 생각합니다."
        ])
        thumbnail = [
            f"지금 가장 맛있는 {product}", f"좋은 {product}은 다릅니다", f"{origin}에서 바로",
            f"한입에서 느껴지는 {d1}", f"오늘 식탁은 {product}",
        ]
        hashtags = ["#" + x.replace(" ", "") for x in seo[:15]]
        return {
            "product_names": product_names,
            "seo_keywords": seo[:30],
            "shorts_script": shorts,
            "blog_draft": blog,
            "thumbnail_copy": thumbnail,
            "hashtags": hashtags,
        }

    def export_content_bundle(self, folder: Path, data: dict[str, Any], sections: list[dict[str, Any]]) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        package = self.content_package(data, sections)
        product = str(data.get("product_name") or "product").strip().replace("/", "_")
        files: list[Path] = []
        html_path = folder / f"{product}_상세페이지.html"
        self.export_html(html_path, data, sections)
        files.append(html_path)
        txt_path = folder / f"{product}_상세페이지_카피.txt"
        self.export_text(txt_path, sections, self.hooks(data))
        files.append(txt_path)
        content_path = folder / f"{product}_마케팅콘텐츠.txt"
        parts = ["[상품명 후보]"] + package["product_names"] + ["", "[SEO 키워드]", ", ".join(package["seo_keywords"]), "", "[썸네일 문구]"] + package["thumbnail_copy"] + ["", "[쇼츠 대본]", package["shorts_script"], "", "[블로그 초안]", package["blog_draft"], "", "[해시태그]", " ".join(package["hashtags"])]
        content_path.write_text("\n".join(parts), encoding="utf-8-sig")
        files.append(content_path)
        json_path = folder / f"{product}_프로젝트.json"
        json_path.write_text(json.dumps({"input": data, "sections": sections, "content": package}, ensure_ascii=False, indent=2), encoding="utf-8")
        files.append(json_path)
        return files


    def classify_image_files(self, paths: list[str]) -> list[dict[str, Any]]:
        """Classify uploaded product images with transparent filename heuristics.

        This deliberately avoids pretending to perform computer vision. The user can
        review and change every suggestion in the image desk.
        """
        rules = [
            ("packing", ("포장", "박스", "아이스팩", "택배", "송장", "패키지", "packing", "box")),
            ("origin", ("산지", "조업", "어선", "농장", "수확", "바다", "항구", "origin", "farm", "boat")),
            ("prep", ("손질", "세척", "조리과정", "삶기", "굽기", "해동", "prep", "cook")),
            ("option", ("옵션", "구성", "중량", "사이즈", "크기", "세트", "option", "size", "weight")),
            ("food", ("요리", "완성", "플레이팅", "상차림", "접시", "젓가락", "food", "dish", "plate")),
            ("brand", ("로고", "브랜드", "인트로", "엔딩", "cs", "logo", "brand")),
            ("notice", ("안내", "주의", "보관", "배송안내", "notice", "guide")),
        ]
        result=[]
        for raw in paths:
            path=Path(raw)
            name=path.stem.lower().replace("_"," ").replace("-"," ")
            group="main"; reason="파일명에 특정 용도 단서가 없어 메인 상품 사진으로 제안"
            for candidate, keywords in rules:
                matched=[x for x in keywords if x.lower() in name]
                if matched:
                    group=candidate; reason=f"파일명 키워드 감지: {', '.join(matched[:3])}"; break
            result.append({"path":str(path),"name":path.name,"group":group,"reason":reason,"assigned":False})
        return result

    def image_audit(self, assets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        required = {"main":3,"food":3,"origin":2,"packing":2,"prep":2,"option":1,"brand":1}
        counts={k:0 for k in required}
        for section_key, items in (assets or {}).items():
            spec=next((x for x in SECTION_SPECS if x[0]==section_key),None)
            group=spec[2] if spec else "main"
            if group not in counts: continue
            counts[group]+=sum(1 for x in items if x.get("status")=="ready" and x.get("path"))
        missing={k:max(0,v-counts.get(k,0)) for k,v in required.items()}
        labels={"main":"메인·원물","food":"완성 음식","origin":"산지·생산","packing":"포장·배송","prep":"손질·조리 과정","option":"구성·옵션","brand":"브랜드"}
        tips=[f"{labels[k]} 사진 {n}장 추가 권장" for k,n in missing.items() if n]
        return {"counts":counts,"required":required,"missing":missing,"tips":tips or ["필수 이미지 구성이 충분합니다."]}

    def export_image_manifest(self, path: Path, assets: dict[str, list[dict[str, Any]]]) -> None:
        audit=self.image_audit(assets)
        rows=["[비선상회 이미지 구성표]",""]
        for key,label,group,count,desc in SECTION_SPECS:
            rows.append(f"[{label}] 권장 {count}장 · {desc}")
            items=(assets or {}).get(key,[])
            if not items: rows.append("- 등록 이미지 없음")
            for idx,item in enumerate(items,1):
                state=item.get("status","empty")
                source=item.get("source","")
                value=item.get("path") or item.get("prompt") or ""
                rows.append(f"- 슬롯 {idx}: {state} / {source} / {value}")
            rows.append("")
        rows += ["[이미지 점검]"] + [f"- {x}" for x in audit["tips"]]
        path.write_text("\n".join(rows),encoding="utf-8-sig")

    @staticmethod
    def _image_uri(path: str) -> str:
        p=Path(path)
        if not p.exists(): return ""
        mime=mimetypes.guess_type(p.name)[0] or "image/jpeg"
        return f"data:{mime};base64,"+base64.b64encode(p.read_bytes()).decode("ascii")

    def export_text(self, path: Path, sections: list[dict[str, Any]], hooks: list[str]) -> None:
        parts=["[후킹 후보]"]+[f"{i}. {h}" for i,h in enumerate(hooks,1)]
        for s in sections: parts += ["",f"[{s['label']}]",s['title'],s['body']]
        path.write_text("\n".join(parts),encoding="utf-8-sig")

    def export_html(self, path: Path, data: dict[str, Any], sections: list[dict[str, Any]]) -> None:
        cards=[]
        for sec in sections:
            imgs=[]
            for item in sec.get("assets",[]):
                if item.get("status")=="omit": continue
                uri=self._image_uri(item.get("path", ""))
                if uri: imgs.append(f"<img src='{uri}' alt='{html.escape(sec['label'])}'>")
            gallery=f"<div class='gallery g{min(len(imgs),3)}'>{''.join(imgs)}</div>" if imgs else ""
            body="<br>".join(html.escape(x) for x in sec["body"].splitlines())
            cards.append(f"<section class='{sec['group']}'><div class='eyebrow'>{html.escape(sec['label'])}</div><h2>{html.escape(sec['title'])}</h2><p>{body}</p>{gallery}</section>")
        product=html.escape(str(data.get("product_name") or "비선상회 상품"))
        brand=self.get_brand(); stamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        yt=str(data.get("youtube_url") or "").strip()
        video=""
        if yt:
            vid=yt.split("v=")[-1].split("&")[0].split("/")[-1]
            video=f"<div class='video'><iframe src='https://www.youtube.com/embed/{html.escape(vid)}?autoplay=1&mute=1&loop=1&playlist={html.escape(vid)}&controls=0' allow='autoplay; encrypted-media; picture-in-picture' allowfullscreen></iframe></div>"
        doc=f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{product}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#e9e7e1;font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:#20201d}}.page{{width:760px;max-width:100%;margin:auto;background:#fff}}.video{{aspect-ratio:760/599}}iframe{{width:100%;height:100%;border:0}}section{{padding:74px 54px;text-align:center}}section:nth-child(even){{background:#f7f3e9}}section.brand{{background:#173d35;color:white}}.eyebrow{{font-size:14px;letter-spacing:2px;font-weight:700;opacity:.72;margin-bottom:16px}}h2{{font-size:38px;line-height:1.28;margin:0 0 24px;word-break:keep-all}}p{{font-size:20px;line-height:1.85;margin:0;word-break:keep-all}}.gallery{{display:grid;gap:10px;margin-top:34px}}.g1{{grid-template-columns:1fr}}.g2{{grid-template-columns:1fr 1fr}}.g3{{grid-template-columns:2fr 1fr 1fr}}img{{display:block;width:100%;height:auto;object-fit:cover}}footer{{padding:34px;text-align:center;background:#111;color:#bbb;font-size:13px}}@media(max-width:760px){{h2{{font-size:8vw}}p{{font-size:4.2vw}}section{{padding:12vw 7vw}}}}
</style></head><body><main class='page'>{video}{''.join(cards)}<footer>{html.escape(brand['brand_name'])} · {stamp}</footer></main></body></html>"""
        path.write_text(doc,encoding="utf-8")
