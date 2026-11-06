def reads(cur,employee_id,kind):
    cur.execute('SELECT request_id,version FROM collaboration_reads WHERE employee_id=%s AND kind=%s',(employee_id,kind))
    return {r['request_id']:r['version'] for r in cur.fetchall()}


def acknowledge(cur,employee_id,request_id,kind,version):
    cur.execute('''INSERT INTO collaboration_reads(employee_id,request_id,kind,version) VALUES(%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE version=VALUES(version)''',(employee_id,request_id,kind,version))
