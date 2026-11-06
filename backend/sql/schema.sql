CREATE TABLE IF NOT EXISTS employees (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 login_id VARCHAR(50) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 name VARCHAR(100) NOT NULL,
 department VARCHAR(100) NOT NULL,
 email VARCHAR(255) NOT NULL UNIQUE,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS requests (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 requester_id BIGINT NOT NULL,
 assignee_id BIGINT NOT NULL,
 original_text TEXT NOT NULL,
 request_message TEXT NULL,
 task_content TEXT NOT NULL,
 due_at DATETIME NOT NULL,
 conditions_json JSON NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(requester_id) REFERENCES employees(id),
 FOREIGN KEY(assignee_id) REFERENCES employees(id),
 CHECK(status IN ('PENDING','NEGOTIATING','ACCEPTED','REJECTED','FAILED','CANCELLED')),
 INDEX idx_requests_requester_status(requester_id,status),
 INDEX idx_requests_assignee_status(assignee_id,status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS responses (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL UNIQUE,
 decision VARCHAR(30) NOT NULL,
 reject_reason TEXT NULL,
 responded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(request_id) REFERENCES requests(id),
 CHECK(decision IN ('ACCEPTED','REJECTED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS negotiations (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL,
 round_no INT NOT NULL,
 request_snapshot_json JSON NOT NULL,
 analysis_json JSON NULL,
 alternatives_json JSON NULL,
 consents_json JSON NULL,
 accepted_condition_key VARCHAR(100) NULL,
 accepted_condition_keys_json JSON NULL,
 assignee_comment TEXT NULL,
 requester_feedback TEXT NULL,
 assignee_feedback TEXT NULL,
 selected_alternative_key VARCHAR(100) NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'IN_PROGRESS',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 closed_at DATETIME NULL,
 UNIQUE(request_id,round_no),
 UNIQUE(request_id,id),
 FOREIGN KEY(request_id) REFERENCES requests(id),
 CHECK(round_no>=1),
 CHECK(status IN ('IN_PROGRESS','AGREED','FAILED','CANCELLED')),
 CHECK(closed_at IS NULL OR closed_at>=created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS results (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL UNIQUE,
 negotiation_id BIGINT NULL UNIQUE,
 status VARCHAR(30) NOT NULL,
 agreed_terms_json JSON NULL,
 reason TEXT NULL,
 a_confirmed_at DATETIME NULL,
 b_confirmed_at DATETIME NULL,
 finalized_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(request_id) REFERENCES requests(id),
 FOREIGN KEY(request_id,negotiation_id) REFERENCES negotiations(request_id,id),
 CHECK(status IN ('PENDING_CONFIRMATION','ACCEPTED','REJECTED','FAILED','CANCELLED')),
 CHECK(status<>'ACCEPTED' OR agreed_terms_json IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS schedules (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 employee_id BIGINT NOT NULL,
 requester_id BIGINT NULL,
 result_id BIGINT NULL,
 result_item_key VARCHAR(100) NULL,
 title VARCHAR(255) NOT NULL,
 type VARCHAR(20) NOT NULL,
 start_at DATETIME NOT NULL,
 end_at DATETIME NOT NULL,
 due_at DATETIME NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
 priority VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
 workload VARCHAR(10) NULL,
 is_new BOOLEAN NOT NULL DEFAULT FALSE,
 memo TEXT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE(result_id,result_item_key),
 FOREIGN KEY(employee_id) REFERENCES employees(id),
 FOREIGN KEY(requester_id) REFERENCES employees(id),
 FOREIGN KEY(result_id) REFERENCES results(id),
 CHECK(end_at>start_at),
 CHECK((result_id IS NULL AND result_item_key IS NULL) OR (result_id IS NOT NULL AND result_item_key IS NOT NULL)),
 CHECK(type IN ('PERSONAL','WORK','MEETING')),
 CHECK(status IN ('SCHEDULED','IN_PROGRESS','COMPLETED','CANCELLED')),
 CHECK(priority IN ('LOW','MEDIUM','HIGH')),
 CHECK(workload IS NULL OR workload IN ('LOW','MEDIUM','HIGH')),
 INDEX idx_schedules_employee_time(employee_id,start_at,end_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_sessions (
 token_hash CHAR(64) PRIMARY KEY,
 employee_id BIGINT NOT NULL,
 expires_at DATETIME NOT NULL,
 FOREIGN KEY(employee_id) REFERENCES employees(id),
 INDEX idx_session_expiry(expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS request_attachments (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, request_id BIGINT NOT NULL,
 filename VARCHAR(240) NOT NULL, mime_type VARCHAR(100) NOT NULL, size INT NOT NULL, content LONGBLOB NOT NULL,
 FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS collaboration_reads (
 employee_id BIGINT NOT NULL, request_id BIGINT NOT NULL, kind VARCHAR(10) NOT NULL, version CHAR(64) NOT NULL,
 PRIMARY KEY(employee_id,request_id,kind),
 FOREIGN KEY(employee_id) REFERENCES employees(id), FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
