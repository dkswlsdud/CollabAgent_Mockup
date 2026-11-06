"""demo_service: 업무 규칙과 트랜잭션 처리."""

from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash
from app.services.plan_service import new_alternative, make_items
from app.services.schedule_service import analysis_for, save_schedule_items
from app.shared.serialization import clean, dump
from app.shared.dates import now
from app.database import transaction
from app.repositories import (
    employee_repository,
    negotiation_repository,
    request_repository,
    response_repository,
    result_repository,
    schedule_repository,
    schema_repository,
)

SCENARIOS = [
    ("응답 대기 · 캠페인 썸네일", "PENDING", "2026-11-06T18:00:00"),
    ("바로 수락 · 이벤트 배너", "ACCEPTED", "2026-10-30T18:00:00"),
    ("바로 거절 · 긴급 랜딩페이지", "REJECTED", "2026-11-03T18:00:00"),
    ("조건 조율 · 상세페이지 개편", "NEGOTIATING", "2026-11-10T18:00:00"),
    ("대안 선택 · 뉴스레터 이미지", "SELECTING", "2026-11-11T18:00:00"),
    ("최종 확인 · 브랜드 소개서", "CONFIRMING", "2026-11-12T18:00:00"),
    ("합의 완료 · 파트너 소개 배너", "FINALIZED", "2026-11-13T18:00:00"),
]


def init_db():
    """Add missing tables and seed demo rows. Never delete existing business data."""
    with transaction() as cur:
        for statement in (
            (Path(__file__).resolve().parents[2] / "sql" / "schema.sql")
            .read_text(encoding="utf-8")
            .split(";")
        ):
            if statement.strip():
                schema_repository.apply_schema_statement(cur, statement)
        users = [
            ("김민지", "마케팅팀", "minji.kim@example.com"),
            ("이서준", "디자인팀", "seojun.lee@example.com"),
            ("박지훈", "콘텐츠팀", "jihoon.park@example.com"),
            ("정하은", "디자인팀", "haeun.jung@example.com"),
            ("최유진", "마케팅팀", "yujin.choi@example.com"),
        ]
        ids = {}
        for name, department, email in users:
            employee_repository.insert_demo_employee(
                cur,
                (
                    email.split("@")[0],
                    generate_password_hash("Collab123!"),
                    name,
                    department,
                    email,
                ),
            )
            ids[name] = employee_repository.find_employee_by_email(cur, (email,))["id"]
        demo = [
            (
                "김민지",
                "캠페인 기획 회의",
                "MEETING",
                "2026-10-28 10:00",
                "2026-10-28 11:00",
            ),
            (
                "김민지",
                "11월 프로모션 기획",
                "WORK",
                "2026-10-29 09:00",
                "2026-10-30 12:00",
            ),
            (
                "김민지",
                "홍보 소재 최종 검토",
                "WORK",
                "2026-11-03 13:00",
                "2026-11-03 15:00",
            ),
            (
                "김민지",
                "마케팅 주간 회의",
                "MEETING",
                "2026-11-04 10:00",
                "2026-11-04 11:00",
            ),
            (
                "최유진",
                "광고 성과 분석",
                "WORK",
                "2026-10-28 13:00",
                "2026-10-28 17:00",
            ),
            (
                "최유진",
                "SNS 콘텐츠 기획",
                "WORK",
                "2026-11-05 09:00",
                "2026-11-05 12:00",
            ),
            (
                "이서준",
                "제품 상세페이지 리뉴얼",
                "WORK",
                "2026-11-02 09:00",
                "2026-11-05 17:00",
            ),
            (
                "이서준",
                "SNS 캠페인 이미지 제작",
                "WORK",
                "2026-11-06 09:00",
                "2026-11-06 12:00",
            ),
            (
                "이서준",
                "디자인팀 주간 회의",
                "MEETING",
                "2026-11-04 14:00",
                "2026-11-04 15:00",
            ),
            ("이서준", "연차 휴가", "PERSONAL", "2026-11-09 09:00", "2026-11-09 18:00"),
            (
                "정하은",
                "브랜드 가이드 정리",
                "WORK",
                "2026-10-29 10:00",
                "2026-10-29 17:00",
            ),
            ("정하은", "아이콘 디자인", "WORK", "2026-11-05 10:00", "2026-11-05 15:00"),
            (
                "박지훈",
                "뉴스레터 원고 작성",
                "WORK",
                "2026-11-03 09:00",
                "2026-11-03 17:00",
            ),
        ]
        for name, title, kind, start, end in demo:
            if not schedule_repository.find_demo_schedule(cur, (ids[name], title, start)):
                schedule_repository.insert_demo_schedule(
                    cur,
                    (
                        ids[name],
                        title,
                        kind,
                        start,
                        end,
                        end if kind == "WORK" else None,
                    ),
                )
        conditions = [
            dict(key="deadline", label="마감", constraint="HARD"),
            dict(key="quantity", label="수량", value=5, unit="개", constraint="SOFT"),
            dict(
                key="specification", label="규격", value="1200×600px", constraint="HARD"
            ),
        ]
        title = "신제품 홍보 배너 제작 · DB 데모"
        if not request_repository.find_demo_request(cur, (ids["김민지"], title)):
            due = datetime(2026, 11, 6, 18)
            row = dict(
                id=request_repository.insert_demo_request(
                    cur,
                    (
                        ids["김민지"],
                        ids["이서준"],
                        "11월 6일까지 홍보 배너 5개를 만들어주세요. 규격은 1200×600px입니다.",
                        title,
                        due,
                        dump(conditions),
                    ),
                ),
                requester_id=ids["김민지"],
                assignee_id=ids["이서준"],
                task_content=title,
                due_at=due,
                conditions_json=conditions,
            )
        title = "파트너 소개 배너 제작 · 빠른 합의 테스트"
        if not request_repository.find_demo_request(cur, (ids["김민지"], title)):
            due = datetime(2026, 11, 13, 18)
            row = dict(
                id=request_repository.insert_demo_request(
                    cur,
                    (
                        ids["김민지"],
                        ids["이서준"],
                        "11월 13일까지 파트너 소개 배너 5개를 만들어주세요.",
                        title,
                        due,
                        dump(conditions),
                    ),
                ),
                requester_id=ids["김민지"],
                assignee_id=ids["이서준"],
                task_content=title,
                due_at=due,
                conditions_json=conditions,
            )
        print("DB initialized. Demo account: minji.kim / Collab123!")
    seed_demo_scenarios()


def seed_demo_scenarios():
    added = 0
    with transaction() as cur:
        employees = {
            row["email"]: row
            for row in employee_repository.find_demo_employees(
                cur, ("minji.kim@example.com", "seojun.lee@example.com")
            )
        }
        requester = employees["minji.kim@example.com"]
        assignee = employees["seojun.lee@example.com"]
        conditions = [
            dict(key="deadline", label="마감", constraint="HARD"),
            dict(key="quantity", label="수량", value=5, unit="개", constraint="SOFT"),
            dict(
                key="specification", label="규격", value="1200×600px", constraint="HARD"
            ),
        ]
        for label, stage, due_at in SCENARIOS:
            title = label + " · 시연"
            if request_repository.find_demo_request(cur, (requester["id"], title)):
                continue
            due = datetime.fromisoformat(due_at)
            status = (
                stage
                if stage in {"PENDING", "ACCEPTED", "REJECTED"}
                else "ACCEPTED" if stage == "FINALIZED" else "NEGOTIATING"
            )
            request_id = request_repository.insert_demo_request_with_status(
                cur,
                (
                    requester["id"],
                    assignee["id"],
                    f"{due:%m월 %d일}까지 이미지 5개를 1200×600px 규격으로 제작해주세요.",
                    title,
                    due,
                    dump(conditions),
                    status,
                ),
            )
            added += 1
            row = clean(request_repository.find_seed_request(cur, (request_id,)))
            if stage == "PENDING":
                continue
            reason = "기존 업무 일정 때문에 원래 조건으로 진행하기 어렵습니다."
            response_repository.insert_response(
                cur,
                (
                    request_id,
                    "ACCEPTED" if stage == "ACCEPTED" else "REJECTED",
                    None if stage == "ACCEPTED" else reason,
                ),
            )
            plan = new_alternative(
                row,
                1,
                "A안 · 원 조건 유지",
                make_items(row, 5),
                "원래 수량과 규격을 유지합니다.",
            )["plan_json"]
            if stage in {"ACCEPTED", "REJECTED"}:
                result_id = result_repository.insert_demo_direct_result(
                    cur,
                    (
                        request_id,
                        status,
                        dump(plan) if stage == "ACCEPTED" else None,
                        None if stage == "ACCEPTED" else reason,
                        datetime(2026, 10, 29, 9) if stage == "ACCEPTED" else None,
                    ),
                )
                if stage == "ACCEPTED":
                    save_schedule_items(cur, row, result_id, plan, allow_past=True)
                continue
            if stage == "FINALIZED":
                negotiation_repository.insert_demo_failed_round(
                    cur,
                    (
                        request_id,
                        dump(row),
                        "원 규격은 유지하고 납품 항목을 나눠 검토해주세요.",
                    ),
                )
            alternatives = (
                []
                if stage == "NEGOTIATING"
                else [
                    new_alternative(
                        row,
                        1,
                        "A안 · 원 조건 유지",
                        make_items(row, 5),
                        "원래 수량과 규격을 유지합니다.",
                    ),
                    new_alternative(
                        row,
                        2,
                        "B안 · 분할 납품",
                        make_items(row, 5, True),
                        "동일한 마감 안에서 두 번에 나눠 납품합니다.",
                    ),
                    new_alternative(
                        row,
                        3,
                        "C안 · 수량 조정",
                        make_items(row, 3),
                        "변경 가능한 수량을 3개로 줄입니다.",
                    ),
                ]
            )
            if alternatives:
                alternatives[0].update(a_selected=True, b_selected=True)
                alternatives[1]["b_selected"] = True
            consents = (
                []
                if not alternatives
                else [
                    dict(
                        id=1,
                        employee_id=requester["id"],
                        employee_name=requester["name"],
                        alternative_id=1,
                        description="원 조건으로 진행하는 대안에 대한 요청자 확인",
                        status="PENDING" if stage == "SELECTING" else "APPROVED",
                    )
                ]
            )
            negotiation_id = negotiation_repository.insert_demo_round(
                cur,
                (
                    request_id,
                    2 if stage == "FINALIZED" else 1,
                    dump(row),
                    dump(analysis_for(cur, assignee["id"], due)),
                    dump(alternatives),
                    dump(consents),
                    "마감과 규격은 유지하고 작업 수량 및 분할 납품을 조율하고 싶습니다.",
                    "1" if stage in {"CONFIRMING", "FINALIZED"} else None,
                    "AGREED" if stage == "FINALIZED" else "IN_PROGRESS",
                    now() if stage == "FINALIZED" else None,
                ),
            )
            if stage in {"CONFIRMING", "FINALIZED"}:
                result_id = result_repository.insert_demo_final_result(
                    cur,
                    (
                        request_id,
                        negotiation_id,
                        "ACCEPTED" if stage == "FINALIZED" else "PENDING_CONFIRMATION",
                        dump(plan),
                        datetime(2026, 10, 29, 10) if stage == "FINALIZED" else None,
                        datetime(2026, 10, 29, 10) if stage == "FINALIZED" else None,
                    ),
                )
                if stage == "FINALIZED":
                    save_schedule_items(cur, row, result_id, plan, allow_past=True)
        incoming_title = "받은 요청 · 디자인 검토 회의 · 시연"
        if not request_repository.find_demo_request(cur, (assignee["id"], incoming_title)):
            request_repository.insert_demo_incoming_request(
                cur,
                (
                    assignee["id"],
                    requester["id"],
                    "11월 16일까지 디자인 검토 의견을 전달해주세요.",
                    incoming_title,
                    datetime(2026, 11, 16, 18),
                    dump(conditions),
                ),
            )
            added += 1
    print(f"Demo scenarios: {added} added (existing rows preserved).")
