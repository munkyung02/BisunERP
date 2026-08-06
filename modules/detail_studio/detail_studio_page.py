from __future__ import annotations

import json
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk

from .detail_studio_service import DEFAULT_BRAND, DetailStudioService


class DetailStudioPage(ttk.Frame):
    FIELD_SPECS = [
        ("product_name","상품명",1),("category","상품 유형",1),("origin","원산지·산지",1),
        ("option_text","중량·옵션",2),("product_dna","상품 DNA (쉼표 구분)",2),
        ("key_point","핵심 장점·선별 기준",3),("customer_worries","고객이 망설이는 이유",3),
        ("why_now","지금 구매해야 하는 이유",2),("production_story","조업·생산·준비 방식",3),
        ("taste_texture","맛·식감",2),("usage_text","먹는 법·활용",3),("prep_text","손질·조리 방법",3),
        ("shipping_text","배송 마감·출고 안내",3),("storage_text","보관 방법",2),("caution_text","주의사항",2),
        ("cta_text","최종 구매 유도",2),("youtube_url","유튜브 URL",1),
    ]

    def __init__(self,parent:tk.Widget,status_callback=None)->None:
        super().__init__(parent,padding=14)
        self.service=DetailStudioService(); self.status_callback=status_callback or (lambda _x:None)
        self.products=[]; self.inputs={}; self.brand_inputs={}; self.asset_rows={}; self.assets={}; self.section_vars={}
        self.sections=[]; self.current_html=None; self.hooks_cache=[]; self.content_cache={}; self.image_queue=[]; self._thumb_refs=[]
        self._build(); self.refresh_products(); self.load_brand(); self.build_modules()

    def _build(self):
        head=ttk.Frame(self); head.pack(fill="x")
        ttk.Label(head,text="Bisun Studio Alpha",font=("맑은 고딕",22,"bold")).pack(side="left")
        ttk.Label(head,text="브랜드·카피·섹션·이미지 모듈",font=("맑은 고딕",10)).pack(side="left",padx=14,pady=(8,0))
        selector=ttk.LabelFrame(self,text="상품 프로젝트",padding=8); selector.pack(fill="x",pady=(12,8))
        self.product_var=tk.StringVar(); self.product_combo=ttk.Combobox(selector,textvariable=self.product_var,state="readonly",width=55)
        self.product_combo.pack(side="left",padx=(0,6)); self.product_combo.bind("<<ComboboxSelected>>",self._on_product_selected)
        ttk.Button(selector,text="상품 새로고침",command=self.refresh_products).pack(side="left")
        ttk.Button(selector,text="AI 인터뷰 시작",command=self.start_interview).pack(side="left",padx=5)
        ttk.Button(selector,text="전체 초안 생성",command=self.generate_all).pack(side="right")
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True)
        self.tab_product=ttk.Frame(self.tabs,padding=12); self.tab_brand=ttk.Frame(self.tabs,padding=12)
        self.tab_interview=ttk.Frame(self.tabs,padding=10); self.tab_modules=ttk.Frame(self.tabs,padding=10); self.tab_result=ttk.Frame(self.tabs,padding=10); self.tab_content=ttk.Frame(self.tabs,padding=10); self.tab_images=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.tab_product,text="1 상품·판매전략"); self.tabs.add(self.tab_interview,text="2 AI 인터뷰"); self.tabs.add(self.tab_brand,text="3 브랜드·CS")
        self.tabs.add(self.tab_modules,text="4 섹션·이미지"); self.tabs.add(self.tab_result,text="5 카피·출력"); self.tabs.add(self.tab_content,text="6 쇼츠·블로그·SEO"); self.tabs.add(self.tab_images,text="7 이미지 자동정리")
        self._build_product(); self._build_interview(); self._build_brand(); self._build_modules_tab(); self._build_result(); self._build_content(); self._build_image_desk()

    def _scroll_frame(self,parent):
        c=tk.Canvas(parent,highlightthickness=0); sb=ttk.Scrollbar(parent,orient="vertical",command=c.yview); inner=ttk.Frame(c)
        inner.bind("<Configure>",lambda _e:c.configure(scrollregion=c.bbox("all"))); c.create_window((0,0),window=inner,anchor="nw")
        c.configure(yscrollcommand=sb.set); c.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y"); return inner

    def _build_product(self):
        inner=self._scroll_frame(self.tab_product)
        for key,label,height in self.FIELD_SPECS:
            ttk.Label(inner,text=label,font=("맑은 고딕",10,"bold")).pack(anchor="w",pady=(7,2))
            w=tk.Text(inner,height=height,width=105,wrap="word",font=("맑은 고딕",10)); w.pack(fill="x"); self.inputs[key]=w

    def _build_interview(self):
        top=ttk.Frame(self.tab_interview); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="상품 맞춤 질문 만들기",command=self.start_interview).pack(side="left",padx=3)
        ttk.Button(top,text="답변을 상품정보에 반영",command=self.apply_interview).pack(side="left",padx=3)
        ttk.Button(top,text="누락정보 점검",command=self.audit_interview).pack(side="left",padx=3)
        ttk.Button(top,text="판매전략 요약",command=self.preview_strategy).pack(side="left",padx=3)
        ttk.Label(top,text="상품 1개에 필요한 질문만 확인한 뒤 생성합니다.").pack(side="right")
        pane=ttk.Panedwindow(self.tab_interview,orient="horizontal"); pane.pack(fill="both",expand=True)
        left=ttk.Frame(pane,padding=(0,0,8,0)); right=ttk.Frame(pane,padding=(8,0,0,0)); pane.add(left,weight=2); pane.add(right,weight=1)
        self.interview_canvas=tk.Canvas(left,highlightthickness=0); sb=ttk.Scrollbar(left,orient="vertical",command=self.interview_canvas.yview)
        self.interview_inner=ttk.Frame(self.interview_canvas); self.interview_inner.bind("<Configure>",lambda _e:self.interview_canvas.configure(scrollregion=self.interview_canvas.bbox("all")))
        self.interview_canvas.create_window((0,0),window=self.interview_inner,anchor="nw"); self.interview_canvas.configure(yscrollcommand=sb.set)
        self.interview_canvas.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        ttk.Label(right,text="AI MD 요약",font=("맑은 고딕",12,"bold")).pack(anchor="w",pady=(0,6))
        self.strategy_result=tk.Text(right,wrap="word",font=("맑은 고딕",10),padx=10,pady=10); self.strategy_result.pack(fill="both",expand=True)
        self.interview_widgets={}; self.interview_questions=[]

    def start_interview(self):
        for child in self.interview_inner.winfo_children(): child.destroy()
        self.interview_widgets={}; data=self._data(); self.interview_questions=self.service.interview_questions(data)
        for i,q in enumerate(self.interview_questions,1):
            box=ttk.LabelFrame(self.interview_inner,text=f"Q{i}. {q['question']}",padding=8); box.pack(fill="x",pady=5)
            if q.get("type")=="choice":
                var=tk.StringVar(value=q.get("choices",[""])[0]); w=ttk.Combobox(box,textvariable=var,state="readonly",values=q.get("choices",[]),width=45); w.pack(fill="x"); self.interview_widgets[q["key"]]=var
            else:
                w=tk.Text(box,height=3,wrap="word",font=("맑은 고딕",10)); w.pack(fill="x"); self.interview_widgets[q["key"]]=w
        self.strategy_result.delete("1.0","end"); self.strategy_result.insert("1.0",f"{data.get('product_name') or '상품'} 맞춤 질문 {len(self.interview_questions)}개를 만들었습니다.\n답변 후 '답변을 상품정보에 반영'을 누르세요.")
        self.tabs.select(self.tab_interview)

    def _interview_answers(self):
        answers={}
        for key,w in self.interview_widgets.items():
            answers[key]=w.get().strip() if isinstance(w,tk.StringVar) else w.get("1.0","end").strip()
        return answers

    def apply_interview(self):
        if not self.interview_widgets: self.start_interview(); return
        current=self._data(); updated=self.service.apply_interview_answers(current,self._interview_answers())
        for key,w in self.inputs.items():
            if key in updated and updated[key] is not None: self._set(self.inputs,key,str(updated[key]))
        self.preview_strategy();self.status_callback("AI 인터뷰 답변을 상품 판매전략에 반영했습니다.")

    def audit_interview(self):
        missing=self.service.missing_check(self._data())
        text="[누락정보 점검]\n"+("\n".join(f"- {x}" for x in missing) if missing else "필수 정보가 충분합니다. 바로 생성할 수 있습니다.")
        self.strategy_result.delete("1.0","end"); self.strategy_result.insert("1.0",text); self.tabs.select(self.tab_interview)

    def preview_strategy(self):
        data = self._data()

        summary = self.service.strategy_summary(data)
        md = self.service.md_analysis(data)

        playbook = self.service.playbook.build(
            product=data,
            interview=data.get("interview_answers", {}),
            brand=data.get("brand", {}),
        )

        score = playbook.get("score", 0)
        improvements = playbook.get("improvements", [])
        grade = playbook.get("grade", "D")
        feedback = playbook.get("feedback", [])
                    

        text = (
            f"[이번 상품 판매전략]\n\n"
            f"상품: {summary['product']}\n"
            f"주력 판매축: {summary['axis']}\n"
            f"핵심 타깃: {summary['target']}\n"
            f"강점: {' · '.join(summary['strengths'])}\n"
            f"누락 항목: {summary['risk_count']}개\n\n"
            f"[추천 방향]\n"
            f"{summary['recommendation']}\n\n"
            f"[생성 전 보완]\n"
            + (
                "\n".join(f"- {x}" for x in summary["missing"])
                if summary["missing"]
                else "- 바로 생성 가능합니다."
            )
        )

        text += (
            f"\n\n========================\n\n"
            f"[AI MD 분석]\n\n"
            f"상품성 점수: {md['score']}점\n"
            f"추천 전략: {md['strategy']}\n\n"
            f"[추천사항]"
        )

        if md["tips"]:
            for tip in md["tips"]:
                text += f"\n✔ {tip}"
        else:
            text += "\n✔ 기본 상품 정보가 충분합니다."

        if playbook["missing"]:
            text += "\n\n[AI 부족한 정보]"

            for item in playbook["missing"]:
                text += f"\n□ {item}"
        else:
            text += "\n\n[AI 부족한 정보]\n✔ 필수 정보가 충분합니다."

        text += f"\n\n🏆 AI 등급 : {grade}"
        text += f"\n🎯 AI 완성도 : {score}점\n"

        if improvements:
            text += "\n추가하면 좋은 정보\n"

            labels = {
                "origin": "원산지",
                "key_point": "핵심 장점",
                "taste_texture": "맛·식감",
                "production_story": "생산 스토리",
                "usage_text": "먹는 방법",
                "customer_worries": "고객 불안 요소",
                "shipping_text": "배송 안내",
                "option_text": "옵션 정보",
                "prep_text": "손질 방법",
                "caution_text": "주의사항",
            }

            for item in improvements:
                text += f"\n□ {labels.get(item, item)}"
        else:
            text += "\n✅ 판매에 필요한 핵심 정보가 충분합니다."

        text += "\n\n========================"
        text += "\n\n[AI MD 피드백]"

        for item in feedback:
            text += f"\n✔ {item}"

        self.strategy_result.delete("1.0", "end")
        self.strategy_result.insert("1.0", text)
        self.tabs.select(self.tab_interview)


    def _build_brand(self):
        inner=self._scroll_frame(self.tab_brand)
        fields=[("brand_name","브랜드명",1),("slogan","대표 슬로건",2),("intro_text","브랜드 인트로 기본문",3),
                ("quality_text","비선상회 품질 기준 (줄바꿈)",6),("customer_phone","고객센터 전화번호",1),
                ("customer_hours","상담 가능 시간",2),("shipping_policy","공통 배송 안내",3),("cs_policy","공통 CS 안내",5)]
        for key,label,height in fields:
            ttk.Label(inner,text=label,font=("맑은 고딕",10,"bold")).pack(anchor="w",pady=(7,2))
            w=tk.Text(inner,height=height,width=105,wrap="word",font=("맑은 고딕",10)); w.pack(fill="x"); self.brand_inputs[key]=w
        ttk.Button(inner,text="브랜드 고정값 저장",command=self.save_brand).pack(anchor="e",pady=12)

    def _build_modules_tab(self):
        top=ttk.Frame(self.tab_modules); top.pack(fill="x")
        ttk.Label(top,text="체크한 섹션만 생성됩니다. 각 이미지 슬롯은 업로드·AI 프롬프트·생략 중 선택합니다.").pack(side="left")
        ttk.Button(top,text="모듈 새로 만들기",command=self.build_modules).pack(side="right")
        self.module_wrap=ttk.Frame(self.tab_modules); self.module_wrap.pack(fill="both",expand=True,pady=(8,0))

    def _build_result(self):
        bar=ttk.Frame(self.tab_result); bar.pack(fill="x",pady=(0,8))
        ttk.Button(bar,text="전체 초안 생성",command=self.generate_all).pack(side="left",padx=3)
        ttk.Button(bar,text="TXT 저장",command=self.save_txt).pack(side="left",padx=3)
        ttk.Button(bar,text="760px HTML 저장",command=self.save_html).pack(side="left",padx=3)
        ttk.Button(bar,text="브라우저 미리보기",command=self.preview).pack(side="left",padx=3)
        ttk.Button(bar,text="프로젝트 저장",command=self.save_project).pack(side="left",padx=3)
        ttk.Button(bar,text="저장 프로젝트 불러오기",command=self.open_projects).pack(side="left",padx=3)

        hookbar=ttk.LabelFrame(self.tab_result,text="메인 훅 즉시 교체",padding=7); hookbar.pack(fill="x",pady=(0,8))
        self.hook_var=tk.StringVar(); self.hook_combo=ttk.Combobox(hookbar,textvariable=self.hook_var,state="readonly",width=78)
        self.hook_combo.pack(side="left",fill="x",expand=True); self.hook_combo.bind("<<ComboboxSelected>>",lambda _e:self.apply_hook())
        ttk.Button(hookbar,text="선택 훅 적용",command=self.apply_hook).pack(side="left",padx=4)
        ttk.Button(hookbar,text="좋은 카피로 저장",command=self.save_favorite_hook).pack(side="left",padx=4)

        scorebar=ttk.Frame(self.tab_result); scorebar.pack(fill="x",pady=(0,8))
        self.score_var=tk.StringVar(value="판매점수: 초안 생성 전")
        self.progress_var = tk.StringVar(value="대기 중")

        ttk.Label(
            scorebar,
            textvariable=self.progress_var,
            foreground="blue"
        ).pack(side="left", padx=20)

        self.progress = ttk.Progressbar(
            scorebar,
            mode="determinate",
            length=250,
            maximum=100
        )

        self.progress.pack(side="right", padx=10)
        ttk.Label(scorebar,textvariable=self.score_var,font=("맑은 고딕",12,"bold")).pack(side="left")
        ttk.Button(scorebar,text="판매점수 다시 계산",command=self.refresh_score).pack(side="right")

        pane=ttk.Panedwindow(self.tab_result,orient="horizontal"); pane.pack(fill="both",expand=True)
        left=ttk.Frame(pane,padding=(0,0,7,0)); right=ttk.Frame(pane,padding=(7,0,0,0)); pane.add(left,weight=1); pane.add(right,weight=2)
        ttk.Label(left,text="섹션 순서·편집",font=("맑은 고딕",11,"bold")).pack(anchor="w",pady=(0,5))
        self.section_tree=ttk.Treeview(left,columns=("title",),show="tree headings",height=18)
        self.section_tree.heading("#0",text="순서"); self.section_tree.heading("title",text="섹션 제목")
        self.section_tree.column("#0",width=55,anchor="center"); self.section_tree.column("title",width=240)
        self.section_tree.pack(fill="both",expand=True); self.section_tree.bind("<Double-1>",lambda _e:self.edit_selected_section())
        editbar=ttk.Frame(left); editbar.pack(fill="x",pady=5)
        ttk.Button(editbar,text="위로",command=lambda:self.move_section(-1)).pack(side="left",padx=2)
        ttk.Button(editbar,text="아래로",command=lambda:self.move_section(1)).pack(side="left",padx=2)
        ttk.Button(editbar,text="내용 편집",command=self.edit_selected_section).pack(side="left",padx=2)
        ttk.Button(editbar,text="섹션 제외",command=self.remove_selected_section).pack(side="left",padx=2)
        ttk.Label(right,text="전체 카피·검수 결과",font=("맑은 고딕",11,"bold")).pack(anchor="w",pady=(0,5))
        self.result=tk.Text(right,wrap="word",font=("맑은 고딕",11),padx=12,pady=12); self.result.pack(fill="both",expand=True)

    def _build_content(self):
        bar=ttk.Frame(self.tab_content); bar.pack(fill="x",pady=(0,8))
        ttk.Button(bar,text="마케팅 콘텐츠 생성",command=self.generate_content).pack(side="left",padx=3)
        ttk.Button(bar,text="전체 업로드 패키지 저장",command=self.export_bundle).pack(side="left",padx=3)
        ttk.Button(bar,text="전체 복사",command=self.copy_content).pack(side="left",padx=3)
        ttk.Label(bar,text="상품명·SEO·썸네일·쇼츠·블로그를 한 번에 생성합니다.").pack(side="right")
        self.content_result=tk.Text(self.tab_content,wrap="word",font=("맑은 고딕",11),padx=12,pady=12)
        self.content_result.pack(fill="both",expand=True)

    def _build_image_desk(self):
        bar=ttk.Frame(self.tab_images); bar.pack(fill="x",pady=(0,8))
        ttk.Button(bar,text="사진 여러 장 불러오기",command=self.batch_import_images).pack(side="left",padx=3)
        ttk.Button(bar,text="추천대로 빈 슬롯 배치",command=self.assign_image_queue).pack(side="left",padx=3)
        ttk.Button(bar,text="이미지 점검",command=self.refresh_image_audit).pack(side="left",padx=3)
        ttk.Button(bar,text="구성표 저장",command=self.save_image_manifest).pack(side="left",padx=3)
        ttk.Label(bar,text="파일명 기반 추천이며, 실제 용도는 배치 전 직접 확인합니다.").pack(side="right")
        self.image_audit_var=tk.StringVar(value="사진을 불러오면 자동 분류 결과가 표시됩니다.")
        ttk.Label(self.tab_images,textvariable=self.image_audit_var,font=("맑은 고딕",10,"bold"),wraplength=980).pack(fill="x",pady=(0,8))
        cols=("file","group","reason","status")
        self.image_tree=ttk.Treeview(self.tab_images,columns=cols,show="headings",height=18)
        for c,t,w in (("file","파일명",270),("group","추천 분류",110),("reason","추천 이유",360),("status","배치 상태",100)):
            self.image_tree.heading(c,text=t); self.image_tree.column(c,width=w)
        self.image_tree.pack(fill="both",expand=True)
        edit=ttk.Frame(self.tab_images); edit.pack(fill="x",pady=7)
        ttk.Label(edit,text="선택 사진 분류 변경").pack(side="left")
        self.image_group_var=tk.StringVar(value="main")
        self.image_group_combo=ttk.Combobox(edit,textvariable=self.image_group_var,state="readonly",width=18,values=["main","food","origin","packing","prep","option","brand","notice"])
        self.image_group_combo.pack(side="left",padx=5)
        ttk.Button(edit,text="분류 적용",command=self.change_image_group).pack(side="left")
        ttk.Button(edit,text="선택 사진 미리보기",command=self.preview_queue_image).pack(side="left",padx=5)

    def batch_import_images(self):
        files=filedialog.askopenfilenames(parent=self,filetypes=[("이미지","*.png *.jpg *.jpeg *.webp")])
        if not files:return
        existing={x["path"] for x in self.image_queue}
        self.image_queue += self.service.classify_image_files([x for x in files if x not in existing])
        self._render_image_queue(); self.refresh_image_audit(); self.tabs.select(self.tab_images)

    def _render_image_queue(self):
        for x in self.image_tree.get_children(): self.image_tree.delete(x)
        labels={"main":"메인·원물","food":"완성 음식","origin":"산지·생산","packing":"포장·배송","prep":"손질·조리","option":"구성·옵션","brand":"브랜드","notice":"안내"}
        for i,item in enumerate(self.image_queue):
            self.image_tree.insert("","end",iid=str(i),values=(item["name"],labels.get(item["group"],item["group"]),item["reason"],"배치 완료" if item.get("assigned") else "대기"))

    def change_image_group(self):
        selected=self.image_tree.selection(); group=self.image_group_var.get()
        if not selected:return
        for iid in selected:
            item=self.image_queue[int(iid)]; item["group"]=group; item["reason"]="사용자가 직접 분류"; item["assigned"]=False
        self._render_image_queue()

    def preview_queue_image(self):
        selected=self.image_tree.selection()
        if not selected:return
        item=self.image_queue[int(selected[0])]; win=tk.Toplevel(self); win.title(item["name"]); win.geometry("760x680")
        image=Image.open(item["path"]); image.thumbnail((720,600)); photo=ImageTk.PhotoImage(image); self._thumb_refs.append(photo)
        ttk.Label(win,image=photo).pack(fill="both",expand=True,padx=10,pady=10)
        ttk.Label(win,text=f"추천: {item['group']} · {item['reason']}").pack(pady=(0,10))

    def assign_image_queue(self):
        group_sections={}
        for key,label,group,count,desc in self.service.section_specs(): group_sections.setdefault(group,[]).append((key,count))
        assigned=0
        for item in self.image_queue:
            if item.get("assigned"): continue
            targets=group_sections.get(item["group"],[])
            placed=False
            for key,count in targets:
                for no in range(1,count+1):
                    slot=self._ensure_slot(key,no)
                    if slot.get("status") not in ("ready",):
                        slot.update(path=item["path"],source="batch_upload",status="ready",prompt="")
                        status=self.asset_rows.get((key,no))
                        if status: status.set(f"슬롯 {no}: {Path(item['path']).name}")
                        item["assigned"]=True; assigned+=1; placed=True; break
                if placed: break
        self._render_image_queue(); self.refresh_image_audit()
        messagebox.showinfo("자동 배치",f"빈 이미지 슬롯에 {assigned}장을 배치했습니다.\n남은 사진은 분류 또는 슬롯 상태를 확인해 주세요.",parent=self)

    def refresh_image_audit(self):
        audit=self.service.image_audit(self.assets)
        counts=" · ".join(f"{k} {v}장" for k,v in audit["counts"].items())
        self.image_audit_var.set(f"현재 등록: {counts}  |  "+" / ".join(audit["tips"]))
        if self.sections:self.refresh_score()

    def save_image_manifest(self):
        product=self._data().get("product_name") or "상품"
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".txt",initialfile=f"{product}_이미지_구성표.txt")
        if path:self.service.export_image_manifest(Path(path),self.assets); self.status_callback("이미지 구성표 저장 완료")

    def generate_content(self):
        self._ensure_generated()
        d=self._data(); self.content_cache=self.service.content_package(d,self.sections)
        c=self.content_cache
        parts=["[상품명 후보]"]+[f"{i}. {x}" for i,x in enumerate(c["product_names"],1)]
        parts += ["","[SEO 키워드]",", ".join(c["seo_keywords"]),"","[썸네일 문구]"] + [f"- {x}" for x in c["thumbnail_copy"]]
        parts += ["","[쇼츠 대본]",c["shorts_script"],"","[블로그 초안]",c["blog_draft"],"","[해시태그]"," ".join(c["hashtags"])]
        self.content_result.delete("1.0","end"); self.content_result.insert("1.0","\n".join(parts))
        if self.tabs.select() != str(self.tab_result):
            self.tabs.select(self.tab_content)

        self.status_callback("쇼츠·블로그·SEO 콘텐츠 생성 완료")

    def copy_content(self):
        text=self.content_result.get("1.0","end").strip()
        if not text:
            self.generate_content(); text=self.content_result.get("1.0","end").strip()
        self.clipboard_clear(); self.clipboard_append(text)
        self.status_callback("마케팅 콘텐츠를 클립보드에 복사했습니다.")

    def export_bundle(self):
        self._ensure_generated()
        folder=filedialog.askdirectory(parent=self,title="업로드 패키지를 저장할 폴더 선택")
        if not folder: return
        files=self.service.export_content_bundle(Path(folder),self._data(),self.sections)
        messagebox.showinfo("패키지 저장 완료",f"{len(files)}개 파일을 저장했습니다.\n\n"+"\n".join(p.name for p in files),parent=self)
        self.status_callback("상세페이지·쇼츠·블로그·SEO 패키지 저장 완료")

    def refresh_products(self):
        self.products=self.service.get_products(); vals=[f"{p.get('product_name')}{' / '+p.get('option_name') if p.get('option_name') else ''}" for p in self.products]
        self.product_combo["values"]=vals
        if vals and self.product_combo.current()<0: self.product_combo.current(0); self._on_product_selected()
        self.status_callback(f"Bisun Studio: 상품 {len(vals)}건")

    def _set(self,store,key,val):
        w=store[key]; w.delete("1.0","end"); w.insert("1.0",val or "")

    def _on_product_selected(self,_e=None):
        i=self.product_combo.current()
        if 0<=i<len(self.products):
            p=self.products[i]; self._set(self.inputs,"product_name",p.get("product_name")); self._set(self.inputs,"option_text",p.get("option_name"))

    def load_brand(self):
        b=self.service.get_brand()
        for k in self.brand_inputs: self._set(self.brand_inputs,k,b.get(k,DEFAULT_BRAND.get(k,"")))

    def save_brand(self):
        b={k:w.get("1.0","end").strip() for k,w in self.brand_inputs.items()}; self.service.save_brand(b)
        messagebox.showinfo("저장 완료","비선상회 브랜드·CS 고정값을 저장했습니다.",parent=self)

    def _data(self):
        d={k:w.get("1.0","end").strip() for k,w in self.inputs.items()}; d["brand"]={k:w.get("1.0","end").strip() for k,w in self.brand_inputs.items()}
        i=self.product_combo.current(); d["product_id"]=self.products[i]["id"] if 0<=i<len(self.products) else None
        d["project_name"]=d.get("product_name") or "상세페이지"; d["enabled_sections"]=[k for k,v in self.section_vars.items() if v.get()]
        d["assets"]=self.assets; d["selected_hook"]=getattr(self,"hook_var",tk.StringVar()).get() if hasattr(self,"hook_var") else ""
        return d

    def build_modules(self):
        for c in self.module_wrap.winfo_children(): c.destroy()
        self.asset_rows={}; self.section_vars={}; self.assets={}
        inner=self._scroll_frame(self.module_wrap)
        for key,label,group,count,desc in self.service.section_specs():
            box=ttk.LabelFrame(inner,text=label,padding=7); box.pack(fill="x",pady=5)
            var=tk.BooleanVar(value=True); self.section_vars[key]=var; ttk.Checkbutton(box,text=f"사용 · {desc}",variable=var).pack(anchor="w")
            self.assets[key]=[]
            for no in range(1,count+1):
                row=ttk.Frame(box); row.pack(fill="x",pady=2)
                status=tk.StringVar(value=f"슬롯 {no}: 비어 있음")
                ttk.Label(row,textvariable=status,width=42).pack(side="left")
                ttk.Button(row,text="사진 등록",command=lambda k=key,n=no,s=status:self.add_asset(k,n,s)).pack(side="left",padx=2)
                ttk.Button(row,text="AI 프롬프트",command=lambda k=key,n=no,s=status:self.show_prompt(k,n,s)).pack(side="left",padx=2)
                ttk.Button(row,text="생략",command=lambda k=key,n=no,s=status:self.omit_asset(k,n,s)).pack(side="left",padx=2)
                self.asset_rows[(key,no)]=status

    def _ensure_slot(self,key,no):
        while len(self.assets[key])<no: self.assets[key].append({"path":"","source":"","status":"empty","prompt":""})
        return self.assets[key][no-1]

    def add_asset(self,key,no,status):
        f=filedialog.askopenfilename(parent=self,filetypes=[("이미지","*.png *.jpg *.jpeg *.webp")])
        if f:
            slot=self._ensure_slot(key,no); slot.update(path=f,source="upload",status="ready"); status.set(f"슬롯 {no}: {Path(f).name}")

    def show_prompt(self,key,no,status):
        prompt=self.service.ai_prompt(self._data(),key,no); slot=self._ensure_slot(key,no); slot.update(source="ai_prompt",status="prompt",prompt=prompt)
        win=tk.Toplevel(self); win.title("AI 이미지 생성 프롬프트"); win.geometry("760x420")
        t=tk.Text(win,wrap="word",font=("맑은 고딕",11),padx=12,pady=12); t.pack(fill="both",expand=True); t.insert("1.0",prompt)
        ttk.Button(win,text="클립보드 복사",command=lambda:(self.clipboard_clear(),self.clipboard_append(t.get("1.0","end").strip()),status.set(f"슬롯 {no}: AI 생성 대기"))).pack(pady=8)

    def omit_asset(self,key,no,status):
        slot=self._ensure_slot(key,no); slot.update(status="omit",source="omit",path=""); status.set(f"슬롯 {no}: 생략")

    def generate_all(self):
        d = self._data()

        self.progress["value"] = 0
        self.progress_var.set("상품 분석 중...")
        self.update_idletasks()

        if not d.get("product_name"):
            self.progress_var.set("상품명 입력 필요")
            messagebox.showwarning(
                "확인",
                "상품명을 입력해 주세요.",
                parent=self,
            )
            return

        self.progress["value"] = 20
        self.progress_var.set("AI 판매 전략 생성 중...")
        self.update_idletasks()

        hooks = self.service.hooks(d)

        self.progress["value"] = 45
        self.progress_var.set("메인 훅 구성 중...")
        self.update_idletasks()

        self.hooks_cache = hooks
        self.hook_combo["values"] = hooks
        self.hook_combo.current(0)
        self.hook_var.set(hooks[0])

        self.progress["value"] = 65
        self.progress_var.set("상세페이지 섹션 생성 중...")
        self.update_idletasks()

        self.sections = self.service.build_sections({
            **d,
            "selected_hook": hooks[0],
        })

        self.progress["value"] = 80
        self.progress_var.set("판매력 점검 중...")
        self.update_idletasks()

        self._render_sections()
        self.refresh_score()

        self.progress["value"] = 90
        self.progress_var.set("마케팅 콘텐츠 생성 중...")
        self.update_idletasks()

        self.generate_content()
        self.tabs.select(self.tab_result)

        self.progress["value"] = 100
        self.progress_var.set("전체 초안 생성 완료")
        self.update_idletasks()

        self.status_callback("비선상회 상세페이지 전체 초안 생성 완료")


    def _render_sections(self):
        if hasattr(self,"section_tree"):
            for item in self.section_tree.get_children(): self.section_tree.delete(item)
            for i,sec in enumerate(self.sections,1): self.section_tree.insert("", "end", iid=str(i-1), text=str(i), values=(sec["title"],))
        out=["[메인 훅 후보]"]+[f"{i}. {h}" for i,h in enumerate(self.hooks_cache or self.service.hooks(self._data()),1)]
        for sec in self.sections:
            out += ["",f"[{sec['label']}]",sec["title"],sec["body"],f"필요 이미지: {sec['asset_desc']} / {sec['asset_count']}장"]
        if hasattr(self,"score_data"):
            out += ["","[판매력 검수]"]+[f"{k}: {v}점" for k,v in self.score_data["scores"].items()]
            out += ["","개선 제안"]+[f"- {x}" for x in self.score_data["tips"]]
        self.result.delete("1.0","end"); self.result.insert("1.0","\n".join(out))

    def apply_hook(self):
        hook=self.hook_var.get().strip()
        if not hook or not self.sections: return
        for sec in self.sections:
            if sec.get("key")=="hero": sec["title"]=hook; break
        self.current_html=None; self._render_sections(); self.refresh_score()

    def save_favorite_hook(self):
        hook=self.hook_var.get().strip()
        if not hook: return
        self.service.save_copy("hook",hook,self._data().get("product_name", ""),5)
        messagebox.showinfo("카피 저장","선택한 훅을 비선상회 카피 라이브러리에 저장했습니다.",parent=self)

    def _selected_index(self):
        selected=self.section_tree.selection()
        return int(selected[0]) if selected else None

    def move_section(self,direction):
        idx=self._selected_index()
        if idx is None: return
        target=idx+direction
        if not 0<=target<len(self.sections): return
        self.sections[idx],self.sections[target]=self.sections[target],self.sections[idx]
        self.current_html=None; self._render_sections(); self.section_tree.selection_set(str(target)); self.section_tree.focus(str(target))

    def remove_selected_section(self):
        idx=self._selected_index()
        if idx is None: return
        sec=self.sections[idx]
        if messagebox.askyesno("섹션 제외",f"'{sec['label']}' 섹션을 현재 결과에서 제외할까요?",parent=self):
            self.sections.pop(idx); self.current_html=None; self._render_sections(); self.refresh_score()

    def edit_selected_section(self):
        idx=self._selected_index()
        if idx is None: return
        sec=self.sections[idx]; win=tk.Toplevel(self); win.title(f"섹션 편집 · {sec['label']}"); win.geometry("760x560"); win.transient(self)
        ttk.Label(win,text="제목",font=("맑은 고딕",10,"bold")).pack(anchor="w",padx=12,pady=(12,4))
        title=tk.Text(win,height=3,wrap="word",font=("맑은 고딕",11)); title.pack(fill="x",padx=12); title.insert("1.0",sec["title"])
        ttk.Label(win,text="본문",font=("맑은 고딕",10,"bold")).pack(anchor="w",padx=12,pady=(12,4))
        body=tk.Text(win,height=15,wrap="word",font=("맑은 고딕",11)); body.pack(fill="both",expand=True,padx=12); body.insert("1.0",sec["body"])
        def save():
            sec["title"]=title.get("1.0","end").strip(); sec["body"]=body.get("1.0","end").strip(); self.current_html=None
            self._render_sections(); self.refresh_score(); win.destroy()
        ttk.Button(win,text="수정 내용 적용",command=save).pack(pady=12)

    def refresh_score(self):
        if not self.sections: return
        d=self._data(); d["selected_hook"]=self.hook_var.get().strip()
        self.score_data=self.service.sales_score(d,self.sections)
        detail=" · ".join(f"{k} {v}" for k,v in self.score_data["scores"].items())
        self.score_var.set(f"판매점수 {self.score_data['total']}점  |  {detail}")
        self._render_sections()

    def open_projects(self):
        projects=self.service.list_projects()
        if not projects:
            messagebox.showinfo("프로젝트","저장된 프로젝트가 없습니다.",parent=self); return
        win=tk.Toplevel(self); win.title("저장 프로젝트 불러오기"); win.geometry("680x450"); win.transient(self)
        tree=ttk.Treeview(win,columns=("product","date"),show="headings")
        tree.heading("product",text="상품·프로젝트"); tree.heading("date",text="저장일"); tree.column("product",width=430); tree.column("date",width=180)
        for p in projects: tree.insert("","end",iid=str(p["id"]),values=(p["project_name"],p["updated_at"]))
        tree.pack(fill="both",expand=True,padx=10,pady=10)
        def load():
            sel=tree.selection()
            if not sel:return
            data=self.service.load_project(int(sel[0]))
            if not data:return
            for k,w in self.inputs.items(): self._set(self.inputs,k,data.get(k,""))
            self.assets=data.get("assets") or self.assets
            enabled=set(data.get("enabled_sections") or [])
            for k,v in self.section_vars.items(): v.set(k in enabled if enabled else True)
            self.hooks_cache=self.service.hooks(data); self.hook_combo["values"]=self.hooks_cache
            hook=data.get("selected_hook") or self.hooks_cache[0]; self.hook_var.set(hook)
            self.sections=self.service.build_sections({**data,"selected_hook":hook});
            self._render_sections(); self.refresh_score(); win.destroy(); self.tabs.select(self.tab_result)
        ttk.Button(win,text="선택 프로젝트 불러오기",command=load).pack(pady=(0,10))

    def _ensure_generated(self):
        if not self.sections: self.generate_all()
        return self._data(),self.sections,self.service.hooks(self._data())

    def save_txt(self):
        d,s,h=self._ensure_generated(); p=filedialog.asksaveasfilename(parent=self,defaultextension=".txt",initialfile=f"{d['product_name']}_카피_설계.txt")
        if p:self.service.export_text(Path(p),s,h)

    def save_html(self):
        d,s,_=self._ensure_generated(); p=filedialog.asksaveasfilename(parent=self,defaultextension=".html",initialfile=f"{d['product_name']}_760px_상세페이지.html")
        if p:self.service.export_html(Path(p),d,s); self.current_html=Path(p); self.status_callback(f"HTML 저장 완료: {p}")

    def preview(self):
        d,s,_=self._ensure_generated()
        if not self.current_html:
            self.current_html=Path(__file__).resolve().parent.parent.parent/"output"/"BisunStudio_preview.html"; self.current_html.parent.mkdir(parents=True,exist_ok=True)
            self.service.export_html(self.current_html,d,s)
        webbrowser.open(self.current_html.resolve().as_uri())

    def save_project(self):
        d, s, h = self._ensure_generated()
        text = self.result.get("1.0", "end").strip()
        pid = self.service.save_project(d, text)

        messagebox.showinfo(
            "저장 완료",
            f"{d['product_name']} 프로젝트 #{pid} 저장 완료",
            parent=self,
        )