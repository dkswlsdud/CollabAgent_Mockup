def insert(cur,request_id,name,mime,content):
    cur.execute('INSERT INTO request_attachments(request_id,filename,mime_type,size,content) VALUES(%s,%s,%s,%s,%s)',(request_id,name,mime,len(content),content))


def metadata(cur,request_id):
    cur.execute('SELECT id,filename,size FROM request_attachments WHERE request_id=%s ORDER BY id',(request_id,))
    return cur.fetchall()


def find(cur,attachment_id):
    cur.execute('''SELECT f.*,r.requester_id,r.assignee_id FROM request_attachments f
        JOIN requests r ON r.id=f.request_id WHERE f.id=%s''',(attachment_id,))
    return cur.fetchone()


def authorized_rounds(cur,request_id):
    cur.execute('''SELECT n.* FROM negotiations n JOIN results x ON x.negotiation_id=n.id
        WHERE n.request_id=%s AND n.status IN ('IN_PROGRESS','AGREED')
        AND x.a_confirmed_at IS NOT NULL AND x.b_confirmed_at IS NOT NULL''',(request_id,))
    return cur.fetchall()
