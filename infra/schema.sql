-- UniBrief schema export
-- Generated from Alembic revisions 4ae437bb1586 -> 8f3c0d29a2b7 on 2026-09-01.
-- For review/report only; deploy with alembic upgrade head.

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 4ae437bb1586

CREATE TABLE category (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    name VARCHAR(64) NOT NULL, 
    description VARCHAR(255), 
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_category PRIMARY KEY (id), 
    CONSTRAINT uq_category_name UNIQUE (name)
);

CREATE TABLE platform (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    name VARCHAR(64) NOT NULL, 
    type VARCHAR(32) NOT NULL, 
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_platform PRIMARY KEY (id), 
    CONSTRAINT uq_platform_name UNIQUE (name)
);

CREATE TABLE system_setting (
    setting_key VARCHAR(128) NOT NULL, 
    value_text TEXT NOT NULL, 
    value_type VARCHAR(32) NOT NULL, 
    is_sensitive BOOL NOT NULL DEFAULT '0', 
    description VARCHAR(255), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_system_setting PRIMARY KEY (setting_key)
);

CREATE TABLE user (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    username VARCHAR(64) NOT NULL, 
    display_name VARCHAR(128) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', 
    session_version INTEGER UNSIGNED NOT NULL DEFAULT '1', 
    last_login_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_user PRIMARY KEY (id), 
    CONSTRAINT uq_user_username UNIQUE (username)
);

CREATE TABLE channel (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    user_id BIGINT NOT NULL, 
    platform_id BIGINT NOT NULL, 
    external_id VARCHAR(128) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    channel_type VARCHAR(32) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_channel PRIMARY KEY (id), 
    CONSTRAINT fk_channel_platform_id_platform FOREIGN KEY(platform_id) REFERENCES platform (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_channel_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_channel_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_channel_user_platform_external UNIQUE (user_id, platform_id, external_id)
);

CREATE TABLE information_item (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    user_id BIGINT NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    summary TEXT NOT NULL, 
    source_type VARCHAR(32) NOT NULL, 
    importance TINYINT NOT NULL, 
    confidence NUMERIC(4, 3) NOT NULL, 
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', 
    version INTEGER UNSIGNED NOT NULL DEFAULT '1', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_information_item PRIMARY KEY (id), 
    CONSTRAINT ck_information_item_confidence_range CHECK (confidence BETWEEN 0 AND 1), 
    CONSTRAINT ck_information_item_importance_range CHECK (importance BETWEEN 1 AND 5), 
    CONSTRAINT fk_information_item_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_information_item_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_information_user_status_importance_created ON information_item (user_id, status, importance, created_at);

CREATE TABLE sender (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    user_id BIGINT NOT NULL, 
    platform_id BIGINT NOT NULL, 
    external_id VARCHAR(128) NOT NULL, 
    display_name VARCHAR(255) NOT NULL, 
    source_type VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN', 
    credibility NUMERIC(4, 3) NOT NULL DEFAULT '0.500', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_sender PRIMARY KEY (id), 
    CONSTRAINT ck_sender_credibility_range CHECK (credibility BETWEEN 0 AND 1), 
    CONSTRAINT fk_sender_platform_id_platform FOREIGN KEY(platform_id) REFERENCES platform (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_sender_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_sender_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_sender_user_platform_external UNIQUE (user_id, platform_id, external_id)
);

CREATE TABLE tag (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    user_id BIGINT NOT NULL, 
    name VARCHAR(128) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_tag PRIMARY KEY (id), 
    CONSTRAINT fk_tag_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_tag_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_tag_user_name UNIQUE (user_id, name)
);

CREATE TABLE event (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    information_id BIGINT NOT NULL, 
    start_at DATETIME, 
    deadline DATETIME, 
    event_status VARCHAR(32) NOT NULL DEFAULT 'UPCOMING', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_event PRIMARY KEY (id), 
    CONSTRAINT ck_event_time_present CHECK (start_at IS NOT NULL OR deadline IS NOT NULL), 
    CONSTRAINT ck_event_time_order CHECK (start_at IS NULL OR deadline IS NULL OR deadline >= start_at), 
    CONSTRAINT fk_event_information_id_information_item FOREIGN KEY(information_id) REFERENCES information_item (id) ON DELETE CASCADE, 
    CONSTRAINT uq_event_information_id UNIQUE (information_id)
);

CREATE INDEX ix_event_deadline ON event (deadline);

CREATE INDEX ix_event_status_deadline ON event (event_status, deadline);

CREATE TABLE information_category (
    information_id BIGINT NOT NULL, 
    category_id BIGINT NOT NULL, 
    CONSTRAINT pk_information_category PRIMARY KEY (information_id, category_id), 
    CONSTRAINT fk_information_category_category_id_category FOREIGN KEY(category_id) REFERENCES category (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_information_category_information_id_information_item FOREIGN KEY(information_id) REFERENCES information_item (id) ON DELETE CASCADE
);

CREATE TABLE information_tag (
    user_id BIGINT NOT NULL, 
    information_id BIGINT NOT NULL, 
    tag_id BIGINT NOT NULL, 
    CONSTRAINT pk_information_tag PRIMARY KEY (information_id, tag_id), 
    CONSTRAINT fk_information_tag_user_id_information_item FOREIGN KEY(user_id, information_id) REFERENCES information_item (user_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_information_tag_user_id_tag FOREIGN KEY(user_id, tag_id) REFERENCES tag (user_id, id) ON DELETE RESTRICT
);

CREATE TABLE message (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    user_id BIGINT NOT NULL, 
    channel_id BIGINT NOT NULL, 
    sender_id BIGINT NOT NULL, 
    external_id VARCHAR(191) NOT NULL, 
    content TEXT NOT NULL, 
    sent_at DATETIME NOT NULL, 
    ingested_at DATETIME NOT NULL DEFAULT now(), 
    process_status VARCHAR(32) NOT NULL DEFAULT 'PENDING', 
    processing_started_at DATETIME, 
    CONSTRAINT pk_message PRIMARY KEY (id), 
    CONSTRAINT fk_message_user_id_channel FOREIGN KEY(user_id, channel_id) REFERENCES channel (user_id, id) ON DELETE RESTRICT, 
    CONSTRAINT fk_message_user_id_sender FOREIGN KEY(user_id, sender_id) REFERENCES sender (user_id, id) ON DELETE RESTRICT, 
    CONSTRAINT fk_message_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_message_user_channel_external UNIQUE (user_id, channel_id, external_id), 
    CONSTRAINT uq_message_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_message_status_processing ON message (process_status, processing_started_at);

CREATE INDEX ix_message_user_channel_sent ON message (user_id, channel_id, sent_at);

CREATE INDEX ix_message_user_sender_sent ON message (user_id, sender_id, sent_at);

CREATE INDEX ix_message_user_status_ingested ON message (user_id, process_status, ingested_at);

CREATE TABLE ai_analysis (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    message_id BIGINT NOT NULL, 
    model_name VARCHAR(255) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    useful BOOL, 
    error_code VARCHAR(64), 
    error_message VARCHAR(512), 
    latency_ms INTEGER UNSIGNED, 
    raw_result JSON, 
    raw_response_text MEDIUMTEXT, 
    analyzed_at DATETIME NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_ai_analysis PRIMARY KEY (id), 
    CONSTRAINT fk_ai_analysis_message_id_message FOREIGN KEY(message_id) REFERENCES message (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_analysis_message_analyzed ON ai_analysis (message_id, analyzed_at);

CREATE TABLE event_reminder (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    event_id BIGINT NOT NULL, 
    remind_at DATETIME NOT NULL, 
    reminder_status VARCHAR(32) NOT NULL DEFAULT 'PENDING', 
    is_custom_time BOOL NOT NULL DEFAULT '0', 
    triggered_at DATETIME, 
    read_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_event_reminder PRIMARY KEY (id), 
    CONSTRAINT fk_event_reminder_event_id_event FOREIGN KEY(event_id) REFERENCES event (id) ON DELETE CASCADE, 
    CONSTRAINT uq_event_reminder_event_id UNIQUE (event_id)
);

CREATE INDEX ix_reminder_status_remind_at ON event_reminder (reminder_status, remind_at);

CREATE TABLE message_attachment (
    id BIGINT NOT NULL AUTO_INCREMENT, 
    message_id BIGINT NOT NULL, 
    external_id VARCHAR(191) NOT NULL, 
    file_type VARCHAR(64), 
    file_name VARCHAR(255) NOT NULL, 
    file_url VARCHAR(1024) NOT NULL, 
    storage_key VARCHAR(512), 
    file_size BIGINT UNSIGNED, 
    sha256 VARCHAR(64), 
    download_status VARCHAR(32) NOT NULL DEFAULT 'PENDING', 
    download_attempts INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    downloaded_at DATETIME, 
    last_error VARCHAR(512), 
    extracted_text TEXT, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_message_attachment PRIMARY KEY (id), 
    CONSTRAINT fk_message_attachment_message_id_message FOREIGN KEY(message_id) REFERENCES message (id) ON DELETE CASCADE, 
    CONSTRAINT uq_message_attachment_message_id UNIQUE (message_id, external_id)
);

CREATE TABLE message_information (
    user_id BIGINT NOT NULL, 
    message_id BIGINT NOT NULL, 
    information_id BIGINT NOT NULL, 
    relation_type VARCHAR(32) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    CONSTRAINT pk_message_information PRIMARY KEY (message_id, information_id), 
    CONSTRAINT fk_message_information_user_id_information_item FOREIGN KEY(user_id, information_id) REFERENCES information_item (user_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_message_information_user_id_message FOREIGN KEY(user_id, message_id) REFERENCES message (user_id, id) ON DELETE CASCADE
);

INSERT INTO system_setting (setting_key, value_text, value_type, is_sensitive, description) VALUES ('registration_enabled', 'false', 'BOOLEAN', false, '�Ƿ�������ͨ�û�����ע��');

INSERT INTO system_setting (setting_key, value_text, value_type, is_sensitive, description) VALUES ('admin_session_version', '1', 'INTEGER', true, '����Ա�ỰʧЧ�汾');

INSERT INTO category (name, description, status) VALUES ('�γ�', '�γ̰������ѧ��Ϣ', 'ACTIVE');

INSERT INTO category (name, description, status) VALUES ('��ҵ', '��ҵ���������ύҪ��', 'ACTIVE');

INSERT INTO category (name, description, status) VALUES ('����', '���ԡ������븴ϰ����', 'ACTIVE');

INSERT INTO category (name, description, status) VALUES ('�', 'У԰�������֪ͨ', 'ACTIVE');

INSERT INTO category (name, description, status) VALUES ('֪ͨ', '�������ۺ�֪ͨ', 'ACTIVE');

INSERT INTO category (name, description, status) VALUES ('����', '��δ���������������Ϣ', 'ACTIVE');

INSERT INTO alembic_version (version_num) VALUES ('4ae437bb1586');

-- Running upgrade 4ae437bb1586 -> 8f3c0d29a2b7

CREATE VIEW v_upcoming_events AS
        SELECT
            ii.user_id AS user_id,
            e.id AS event_id,
            e.information_id AS information_id,
            ii.title AS title,
            ii.importance AS importance,
            e.start_at AS start_at,
            e.deadline AS deadline,
            e.event_status AS event_status,
            e.updated_at AS updated_at
        FROM event e
        INNER JOIN information_item ii ON ii.id = e.information_id
        WHERE e.event_status IN ('UPCOMING', 'ONGOING')
          AND ii.status <> 'ARCHIVED';

CREATE VIEW v_channel_effectiveness AS
        SELECT
            c.user_id AS user_id,
            c.id AS channel_id,
            c.platform_id AS platform_id,
            c.name AS channel_name,
            COUNT(DISTINCT m.id) AS message_count,
            COUNT(DISTINCT CASE WHEN mi.information_id IS NOT NULL THEN m.id END)
                AS effective_message_count,
            CASE
                WHEN COUNT(DISTINCT m.id) = 0 THEN 0
                ELSE ROUND(
                    COUNT(DISTINCT CASE WHEN mi.information_id IS NOT NULL THEN m.id END)
                    / COUNT(DISTINCT m.id),
                    4
                )
            END AS effectiveness_rate
        FROM channel c
        LEFT JOIN message m
            ON m.user_id = c.user_id AND m.channel_id = c.id
        LEFT JOIN message_information mi
            ON mi.user_id = m.user_id AND mi.message_id = m.id
        GROUP BY c.user_id, c.id, c.platform_id, c.name;

CREATE VIEW v_category_statistics AS
        SELECT
            ii.user_id AS user_id,
            c.id AS category_id,
            c.name AS category_name,
            COUNT(DISTINCT ii.id) AS information_count
        FROM information_item ii
        INNER JOIN information_category ic ON ic.information_id = ii.id
        INNER JOIN category c ON c.id = ic.category_id
        GROUP BY ii.user_id, c.id, c.name;

CREATE VIEW v_tag_popularity AS
        SELECT
            t.user_id AS user_id,
            t.id AS tag_id,
            t.name AS tag_name,
            COUNT(DISTINCT it.information_id) AS usage_count
        FROM tag t
        LEFT JOIN information_tag it
            ON it.user_id = t.user_id AND it.tag_id = t.id
        GROUP BY t.user_id, t.id, t.name;

CREATE TRIGGER trg_information_item_set_updated_at
        BEFORE UPDATE ON information_item
        FOR EACH ROW
        SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE PROCEDURE sp_channel_statistics(
            IN p_user_id BIGINT,
            IN p_start DATETIME,
            IN p_end DATETIME
        )
        BEGIN
            IF p_start IS NULL OR p_end IS NULL OR p_start >= p_end THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'p_start must be earlier than p_end';
            END IF;

            SELECT
                c.id AS channel_id,
                c.name AS channel_name,
                c.platform_id AS platform_id,
                p.name AS platform_name,
                COUNT(DISTINCT m.id) AS message_count,
                COUNT(DISTINCT CASE WHEN mi.information_id IS NOT NULL THEN m.id END)
                    AS effective_message_count,
                CASE
                    WHEN COUNT(DISTINCT m.id) = 0 THEN 0
                    ELSE ROUND(
                        COUNT(DISTINCT CASE WHEN mi.information_id IS NOT NULL THEN m.id END)
                        / COUNT(DISTINCT m.id),
                        4
                    )
                END AS effectiveness_rate
            FROM channel c
            INNER JOIN platform p ON p.id = c.platform_id
            LEFT JOIN message m
                ON m.user_id = c.user_id
               AND m.channel_id = c.id
               AND m.sent_at >= p_start
               AND m.sent_at < p_end
            LEFT JOIN message_information mi
                ON mi.user_id = m.user_id AND mi.message_id = m.id
            WHERE c.user_id = p_user_id
            GROUP BY c.id, c.name, c.platform_id, p.name
            ORDER BY message_count DESC, c.id ASC;
        END;

UPDATE alembic_version SET version_num='8f3c0d29a2b7' WHERE alembic_version.version_num = '4ae437bb1586';

