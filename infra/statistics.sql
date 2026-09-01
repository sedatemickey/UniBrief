-- UniBrief database advanced objects
-- Source of truth: Alembic revision 8f3c0d29a2b7.
-- Apply through Alembic; this file is for report review and manual inspection only.

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

DELIMITER $$
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
END$$
DELIMITER ;
