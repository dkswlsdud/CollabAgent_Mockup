import mimetypes
from app.database import transaction
from app.shared.errors import fail
from app.shared.serialization import clean
from app.repositories import attachment_repository,negotiation_repository

ALLOWED={'pdf','doc','docx','xls','xlsx','ppt','pptx','txt','csv','png','jpg','jpeg','gif','webp','zip'}


def prepare_uploads(files):
    if len(files)>5:fail('첨부파일은 최대 5개까지 등록할 수 있습니다.')
    result=[]
    total=0
    for file in files:
        name=(file.filename or '').replace('\\','/').split('/')[-1].replace('\r','').replace('\n','').strip()
        if not name or len(name)>240 or name.rsplit('.',1)[-1].lower() not in ALLOWED:
            fail('지원하지 않는 파일입니다. 문서·이미지·ZIP 파일을 첨부해주세요.')
        content=file.stream.read(10*1024*1024+1)
        total+=len(content)
        if not content or len(content)>10*1024*1024 or total>20*1024*1024:fail('파일당 10MB, 전체 20MB 이내로 첨부해주세요.')
        result.append((name,mimetypes.guess_type(name)[0] or 'application/octet-stream',content))
    return result


def download(attachment_id,user):
    with transaction() as cur:
        row=attachment_repository.find(cur,attachment_id)
        if not row:fail('첨부파일이 없습니다.',404)
        allowed=user['id'] in {row['requester_id'],row['assignee_id']}
        if not allowed:
            for n in map(clean,attachment_repository.authorized_rounds(cur,row['request_id'])):
                if n['request_id']==row['request_id']:
                    allowed=any(c['employee_id']==user['id'] and str(c['alternative_id'])==str(n.get('selected_alternative_key')) and c['status']!='WAITING' for c in n.get('consents_json') or [])
                    if allowed:break
        if not allowed:fail('이 첨부파일을 열 수 없습니다.',403)
        return row
