import re
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.WARNING,  # CLI 출력 오염 방지: WARNING 이상만
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("recon_utils")


class ForensicAudit:
    """
    검색 결과 제목에 쿼리 키워드가 실제로 포함되어 있는지 검증.
    띄어쓰기를 무시하는 엄격한 매칭으로 노이즈(관련 없는 논문)를 원천 차단.
    """

    @staticmethod
    def verify_title(query: str, title: str) -> bool:
        if not query or not title:
            return False

        q_clean = query.lower().strip()
        t_clean = title.lower().strip()

        # 1단계: 공백 및 특수문자 제거 후 서브스트링 매칭
        q_norm = q_clean.replace(" ", "")
        t_norm = t_clean.replace(" ", "")
        q_alpha = re.sub(r"[^\w가-힣]", "", q_norm)
        t_alpha = re.sub(r"[^\w가-힣]", "", t_norm)

        if q_alpha and t_alpha and (q_alpha in t_alpha or t_alpha in q_alpha):
            return True

        # 2단계: 원본 서브스트링
        if q_clean in t_clean or t_clean in q_clean:
            return True

        # 3단계: 개별 단어 단위 매칭 (특수문자/문장부호 제외하고 2글자 이상인 단어 대상)
        q_words = [re.sub(r"[^\w가-힣]", "", w) for w in re.split(r"[\s,]+", q_clean) if len(re.sub(r"[^\w가-힣]", "", w)) >= 2]
        if q_words:
            if any(qw in t_alpha for qw in q_words if qw):
                return True

        return False

    @staticmethod
    def audit_results(query: str, results: list[dict], title_key: str = "title") -> tuple[list, list]:
        verified, rejected = [], []
        for item in results:
            title = item.get(title_key, "")
            if ForensicAudit.verify_title(query, title):
                verified.append(item)
            else:
                rejected.append(item)
        return verified, rejected
