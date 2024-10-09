-- Drop existing functions

DROP FUNCTION IF EXISTS public.get_user_by_id(UUID);
DROP FUNCTION IF EXISTS public.get_all_users();
DROP FUNCTION IF EXISTS public.update_user(UUID, JSONB);
DROP FUNCTION IF EXISTS public.insert_user(JSONB);
DROP FUNCTION IF EXISTS public.delete_user(UUID);

DROP FUNCTION IF EXISTS public.get_user_meta(UUID);
DROP FUNCTION IF EXISTS public.get_user_meta_by_id(UUID);
DROP FUNCTION IF EXISTS public.get_all_user_meta();
DROP FUNCTION IF EXISTS public.update_user_meta(UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.insert_user_meta(UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.delete_user_meta(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_meta(UUID, UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.delete_user_meta_by_user_id_and_id(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_forms(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_forms(UUID, UUID, TEXT, action, form_type, TEXT);
DROP FUNCTION IF EXISTS public.delete_user_form(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_nodes(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_nodes(UUID, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_nodes(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_courses(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_courses(UUID, UUID, UUID, TEXT, FLOAT, TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_courses(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_purchases(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_purchases(UUID, UUID, UUID, NUMERIC, TEXT);
DROP FUNCTION IF EXISTS public.delete_user_purchases(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_subscriptions(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_subscriptions(UUID, UUID, TEXT, JSONB, TEXT, INTEGER, BOOLEAN, TIMESTAMP, TIMESTAMP, TIMESTAMP, TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_subscriptions(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_notes(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_notes(UUID, UUID, TEXT, TEXT, TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_notes(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_events(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_events(UUID, UUID, TEXT, TEXT, UUID, TEXT, TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_events(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_videos(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_videos(UUID, UUID, TEXT, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.delete_user_videos(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_user_reports(UUID);
DROP FUNCTION IF EXISTS public.upsert_user_reports(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS public.delete_user_report(UUID, UUID);

DROP FUNCTION IF EXISTS public.get_nodes(p_user_id uuid);
DROP FUNCTION IF EXISTS public.get_nodes_by_name(p_name text);
DROP FUNCTION IF EXISTS public.get_child_nodes_by_parent_name (p_name TEXT);
DROP FUNCTION IF EXISTS public.upsert_nodes(p_id uuid, p_name text, p_type text, p_description text, p_context_info jsonb, p_process_item_level text, p_created_at timestamp);
DROP FUNCTION IF EXISTS public.delete_nodes(p_id uuid);

-- User Context Functions
CREATE OR REPLACE FUNCTION public.get_user_by_id(p_id UUID)
RETURNS TABLE (
  id UUID,
  username TEXT,
  email TEXT,
  form_state JSONB,
  course_state JSONB,
  last_notified TIMESTAMP,
  last_logged_in TIMESTAMP,
  pending BOOLEAN,
  preferences JSONB,
  order_count INTEGER,
  old_user_id TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT u.id, u.username, u.email, u.form_state, u.course_state, u.last_notified, 
         u.last_logged_in, u.pending, u.preferences, u.order_count, u.old_user_id
  FROM public.users u
  WHERE u.id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_all_users()
RETURNS TABLE (
  id UUID,
  username TEXT,
  email TEXT,
  form_state JSONB,
  course_state JSONB,
  last_notified TIMESTAMP,
  last_logged_in TIMESTAMP,
  pending BOOLEAN,
  preferences JSONB,
  order_count INTEGER,
  old_user_id TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT u.id, u.username, u.email, u.form_state, u.course_state, u.last_notified, 
         u.last_logged_in, u.pending, u.preferences, u.order_count, u.old_user_id
  FROM public.users u;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.update_user(
  p_id UUID,
  p_user_data JSONB
)
RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  UPDATE public.users
  SET 
    username = COALESCE(p_user_data->>'username', username),
    email = COALESCE(p_user_data->>'email', email),
    form_state = COALESCE(p_user_data->'form_state', form_state),
    course_state = COALESCE(p_user_data->'course_state', course_state),
    last_notified = COALESCE((p_user_data->>'last_notified')::TIMESTAMP, last_notified),
    last_logged_in = COALESCE((p_user_data->>'last_logged_in')::TIMESTAMP, last_logged_in),
    pending = COALESCE((p_user_data->>'pending')::BOOLEAN, pending),
    preferences = COALESCE(p_user_data->'preferences', preferences),
    order_count = COALESCE((p_user_data->>'order_count')::INTEGER, order_count),
    old_user_id = COALESCE(p_user_data->>'old_user_id', old_user_id)
  WHERE id = p_id
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.insert_user(
  p_user_data JSONB
)
RETURNS UUID AS $$
DECLARE
  new_id UUID;
BEGIN
  INSERT INTO public.users (
    username, email, form_state, course_state, last_notified, last_logged_in, 
    pending, preferences, order_count, old_user_id
  )
  VALUES (
    p_user_data->>'username',
    p_user_data->>'email',
    p_user_data->'form_state',
    p_user_data->'course_state',
    (p_user_data->>'last_notified')::TIMESTAMP,
    (p_user_data->>'last_logged_in')::TIMESTAMP,
    (p_user_data->>'pending')::BOOLEAN,
    p_user_data->'preferences',
    (p_user_data->>'order_count')::INTEGER,
    p_user_data->>'old_user_id'
  )
  RETURNING id INTO new_id;
  
  RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user(p_id UUID)
RETURNS VOID AS $$
BEGIN
  DELETE FROM public.users WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- User Meta Functions
CREATE OR REPLACE FUNCTION public.get_user_meta(p_user_id UUID) 
RETURNS TABLE (
  umeta_id UUID,
  user_id UUID,
  meta_key TEXT,
  meta_value TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT um.umeta_id, um.user_id, um.meta_key, um.meta_value
  FROM public.user_meta um
  WHERE um.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_user_meta_by_id(id UUID) 
RETURNS TABLE (
  umeta_id UUID,
  user_id UUID,
  meta_key TEXT,
  meta_value TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT um.umeta_id, um.user_id, um.meta_key, um.meta_value
  FROM public.user_meta um
  WHERE um.umeta_id = id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_all_user_meta() 
RETURNS TABLE (
  umeta_id UUID,
  user_id UUID,
  meta_key TEXT,
  meta_value TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT um.umeta_id, um.user_id, um.meta_key, um.meta_value
  FROM public.user_meta um;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.update_user_meta(
  p_id UUID,
  p_meta_key TEXT,
  p_meta_value TEXT
) RETURNS VOID AS $$
BEGIN
  UPDATE public.user_meta
  SET meta_key = p_meta_key, meta_value = p_meta_value
  WHERE umeta_id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.insert_user_meta(
  p_user_id UUID,
  p_meta_key TEXT,
  p_meta_value TEXT
) RETURNS UUID AS $$
DECLARE
  new_id UUID;
BEGIN
  INSERT INTO public.user_meta (user_id, meta_key, meta_value)
  VALUES (p_user_id, p_meta_key, p_meta_value)
  RETURNING umeta_id INTO new_id;
  
  RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_meta(p_id UUID) 
RETURNS VOID AS $$
BEGIN
  DELETE FROM public.user_meta WHERE umeta_id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_meta(
  p_id UUID,
  p_user_id UUID,
  p_meta_key TEXT,
  p_meta_value TEXT
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.user_meta (umeta_id, user_id, meta_key, meta_value)
  VALUES (p_id, p_user_id, p_meta_key, p_meta_value)
  ON CONFLICT (umeta_id) DO UPDATE
  SET meta_key = EXCLUDED.meta_key, meta_value = EXCLUDED.meta_value
  RETURNING umeta_id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_meta_by_user_id_and_id(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.user_meta 
  WHERE user_id = p_user_id AND umeta_id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Forms Functions
CREATE OR REPLACE FUNCTION public.get_user_forms(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  title TEXT,
  status action,
  type form_type,
  decrypted_form TEXT,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT f.id, f.title, f.status, f.type, df.decrypted_form, f.created_at, f.updated_at
  FROM public.forms f
  JOIN public.decrypted_forms df ON f.id = df.id
  WHERE f.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_forms(
  p_id UUID,
  p_user_id UUID,
  p_title TEXT,
  p_status action,
  p_type form_type,
  p_form TEXT
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.forms (id, user_id, title, status, type, form, created_at, updated_at)
  VALUES (p_id, p_user_id, p_title, p_status, p_type, p_form, NOW(), NOW())
  ON CONFLICT (id) DO UPDATE
  SET title = EXCLUDED.title, status = EXCLUDED.status, 
      type = EXCLUDED.type, form = EXCLUDED.form, updated_at = NOW()
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_form(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.forms 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Node Context Functions
CREATE OR REPLACE FUNCTION public.get_nodes(p_id UUID) 
RETURNS TABLE (
  id UUID,
  name TEXT,
  type TEXT,
  description TEXT,
  context_info JSON,
  process_item_level BOOLEAN,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE,
  order_sequence INT,
  parent_id INT
) AS $$
BEGIN
  RETURN QUERY
  SELECT nt.id, nt.name, nt.type, nt.description, nt.context_info, nt.process_item_level, nt.created_at, nt.updated_at, nt.order_sequence, nt.parent_id
  FROM public.node_templates nt
  WHERE nt.id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_nodes_by_name(p_name TEXT) 
RETURNS TABLE (
  id INT,
  name TEXT,
  type TEXT,
  description TEXT,
  context_info JSON,
  process_item_level BOOLEAN,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE,
  order_sequence INT,
  parent_id INT
) AS $$
BEGIN
  RETURN QUERY
  SELECT nt.id, nt.name, nt.type, nt.description, nt.context_info, nt.process_item_level, nt.created_at, nt.updated_at, nt.order_sequence, nt.parent_id
  FROM public.node_templates nt
  WHERE nt.name = p_name;
END;
$$ LANGUAGE plpgsql;

CREATE
OR REPLACE FUNCTION public.get_child_nodes_by_parent_name (p_name TEXT) RETURNS TABLE (
  child_node_id INT,
  child_node_name TEXT,
  child_node_type TEXT,
  child_node_description TEXT
) AS $$
BEGIN
    -- Return all child nodes that have the parent_id matching the parent node found by name
    RETURN QUERY
    SELECT 
        nct.id AS child_node_id,
        nct.name AS child_node_name,
        nct.type AS child_node_type,
        nct.description AS child_node_description
    FROM 
        public.node_templates nct
    WHERE 
        nct.parent_id = (SELECT id FROM public.node_templates WHERE name = p_name LIMIT 1);  -- Get the parent node id by name
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_nodes(
  p_id UUID,
  p_name TEXT,
  p_type TEXT,
  p_description TEXT,
  p_context_info JSONB,
  p_process_item_level TEXT,
  p_created_at TIMESTAMP
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.node_templates (id, name, type, description, context_info, process_item_level, created_at)
  VALUES (p_id, p_name, p_type, p_description, p_context_info, p_process_item_level, p_created_at)
  ON CONFLICT (id) DO UPDATE
  SET name = EXCLUDED.name, type = EXCLUDED.type, description = EXCLUDED.description, 
      context_info = EXCLUDED.context_info, process_item_level = EXCLUDED.process_item_level, 
      created_at = EXCLUDED.created_at
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_nodes(
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.node_templates 
  WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Courses Functions
CREATE OR REPLACE FUNCTION public.get_courses(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  course_id UUID,
  status action,
  progress FLOAT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP
) AS $$
BEGIN
  RETURN QUERY
  SELECT uc.id, uc.course_id, uc.status, uc.progress, uc.started_at, uc.completed_at
  FROM public.user_courses uc
  WHERE uc.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Courses Functions
CREATE OR REPLACE FUNCTION public.upsert_user_courses(
  p_id UUID,
  p_user_id UUID,
  p_course_id UUID,
  p_status action,
  p_progress FLOAT,
  p_started_at TIMESTAMP WITH TIME ZONE,
  p_completed_at TIMESTAMP WITH TIME ZONE
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.user_courses (id, user_id, course_id, status, progress, started_at, completed_at)
  VALUES (p_id, p_user_id, p_course_id, p_status, p_progress, p_started_at, p_completed_at)
  ON CONFLICT (id) DO UPDATE
  SET status = EXCLUDED.status, progress = EXCLUDED.progress, completed_at = EXCLUDED.completed_at
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_courses(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.user_courses 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Purchases Functions
CREATE OR REPLACE FUNCTION public.get_user_purchases(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  product_id UUID,
  amount NUMERIC,
  status action,
  created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT p.id, p.product_id, p.amount, p.status, p.created_at
  FROM public.purchases p
  WHERE p.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_purchases(
  p_id UUID,
  p_user_id UUID,
  p_product_id UUID,
  p_amount NUMERIC,
  p_status action
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.purchases (id, user_id, product_id, amount, status, created_at)
  VALUES (p_id, p_user_id, p_product_id, p_amount, p_status, NOW())
  ON CONFLICT (id) DO UPDATE
  SET status = EXCLUDED.status
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_purchases(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.purchases 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Subscriptions Functions
CREATE OR REPLACE FUNCTION public.get_user_subscriptions(p_user_id UUID)
RETURNS TABLE (
  id TEXT,
  status subscription_status,
  price_id TEXT,
  quantity INTEGER,
  cancel_at_period_end BOOLEAN,
  created TIMESTAMP WITH TIME ZONE,
  current_period_start TIMESTAMP WITH TIME ZONE,
  current_period_end TIMESTAMP WITH TIME ZONE,
  ended_at TIMESTAMP WITH TIME ZONE,
  cancel_at TIMESTAMP WITH TIME ZONE,
  canceled_at TIMESTAMP WITH TIME ZONE,
  trial_start TIMESTAMP WITH TIME ZONE,
  trial_end TIMESTAMP WITH TIME ZONE,
  delivery_status delivery_status
) AS $$
BEGIN
  RETURN QUERY
  SELECT s.id, s.status, s.price_id, s.quantity, s.cancel_at_period_end,
         s.created, s.current_period_start, s.current_period_end, s.ended_at,
         s.cancel_at, s.canceled_at, s.trial_start, s.trial_end, s.delivery_status
  FROM public.subscriptions s
  WHERE s.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_subscriptions(
  p_id TEXT,
  p_user_id UUID,
  p_status subscription_status,
  p_price_id TEXT,
  p_quantity INTEGER,
  p_cancel_at_period_end BOOLEAN,
  p_current_period_start TIMESTAMP WITH TIME ZONE,
  p_current_period_end TIMESTAMP WITH TIME ZONE,
  p_ended_at TIMESTAMP WITH TIME ZONE,
  p_cancel_at TIMESTAMP WITH TIME ZONE,
  p_canceled_at TIMESTAMP WITH TIME ZONE,
  p_trial_start TIMESTAMP WITH TIME ZONE,
  p_trial_end TIMESTAMP WITH TIME ZONE,
  p_delivery_status delivery_status
) RETURNS TEXT AS $$
DECLARE
  updated_id TEXT;
BEGIN
  INSERT INTO public.subscriptions (
    id, user_id, status, price_id, quantity, cancel_at_period_end,
    created, current_period_start, current_period_end, ended_at,
    cancel_at, canceled_at, trial_start, trial_end, delivery_status
  )
  VALUES (
    p_id, p_user_id, p_status, p_price_id, p_quantity, p_cancel_at_period_end,
    NOW(), p_current_period_start, p_current_period_end, p_ended_at,
    p_cancel_at, p_canceled_at, p_trial_start, p_trial_end, p_delivery_status
  )
  ON CONFLICT (id) DO UPDATE
  SET status = EXCLUDED.status, price_id = EXCLUDED.price_id,
      quantity = EXCLUDED.quantity, cancel_at_period_end = EXCLUDED.cancel_at_period_end,
      current_period_start = EXCLUDED.current_period_start,
      current_period_end = EXCLUDED.current_period_end,
      ended_at = EXCLUDED.ended_at, cancel_at = EXCLUDED.cancel_at,
      canceled_at = EXCLUDED.canceled_at, trial_start = EXCLUDED.trial_start,
      trial_end = EXCLUDED.trial_end, delivery_status = EXCLUDED.delivery_status
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_subscriptions(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.subscriptions 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Notes Functions
CREATE OR REPLACE FUNCTION public.get_user_notes(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  decrypted_note TEXT,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE,
  event_id UUID
) AS $$
BEGIN
  RETURN QUERY
  SELECT n.id, dn.decrypted_note, n.created_at, n.updated_at, n.event_id
  FROM public.notes n
  JOIN public.decrypted_notes dn ON n.id = dn.note_id
  WHERE n.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_notes(
  p_id UUID,
  p_user_id UUID,
  p_title TEXT,
  p_content TEXT,
  p_created_at TIMESTAMP,
  p_updated_at TIMESTAMP
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.notes (id, user_id, title, content, created_at, updated_at)
  VALUES (p_id, p_user_id, p_title, p_content, p_created_at, p_updated_at)
  ON CONFLICT (id) DO UPDATE
  SET title = EXCLUDED.title, content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_notes(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.notes 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Events Functions
CREATE OR REPLACE FUNCTION public.get_user_events(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  name TEXT,
  type TEXT,
  ref_id UUID,
  description TEXT,
  start_date TIMESTAMP,
  end_date TIMESTAMP,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) AS $$
BEGIN
  RETURN QUERY
  SELECT e.id, e.name, e.type, e.ref_id, e.description, e.start_date, e.end_date, e.created_at, e.updated_at
  FROM public.events e
  WHERE e.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_events(
  p_id UUID,
  p_user_id UUID,
  p_name TEXT,
  p_type TEXT,
  p_ref_id UUID,
  p_description TEXT,
  p_start_date TIMESTAMP,
  p_end_date TIMESTAMP
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.events (id, user_id, name, type, ref_id, description, start_date, end_date, created_at, updated_at)
  VALUES (p_id, p_user_id, p_name, p_type, p_ref_id, p_description, p_start_date, p_end_date, NOW(), NOW())
  ON CONFLICT (id) DO UPDATE
  SET name = EXCLUDED.name, type = EXCLUDED.type, ref_id = EXCLUDED.ref_id, 
      description = EXCLUDED.description, start_date = EXCLUDED.start_date, 
      end_date = EXCLUDED.end_date, updated_at = NOW()
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_events(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.events 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Videos Functions
CREATE OR REPLACE FUNCTION public.get_user_videos(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  title TEXT,
  description TEXT,
  transcript TEXT,
  change_log TEXT,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT v.id, v.title, v.description, v.transcript, v.change_log, v.created_at, v.updated_at
  FROM public.videos v
  WHERE v.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_videos(
  p_id UUID,
  p_user_id UUID,
  p_title TEXT,
  p_description TEXT,
  p_transcript TEXT,
  p_change_log TEXT
) RETURNS UUID AS $$
DECLARE
  updated_id UUID;
BEGIN
  INSERT INTO public.videos (id, user_id, title, description, transcript, change_log, created_at, updated_at)
  VALUES (p_id, p_user_id, p_title, p_description, p_transcript, p_change_log, NOW(), NOW())
  ON CONFLICT (id) DO UPDATE
  SET title = EXCLUDED.title, description = EXCLUDED.description, 
      transcript = EXCLUDED.transcript, change_log = EXCLUDED.change_log, 
      updated_at = NOW()
  RETURNING id INTO updated_id;
  
  RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_videos(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.videos 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_user_reports(p_user_id UUID)
RETURNS TABLE (
  id UUID,
  decrypted_report TEXT,
  created_at TIMESTAMP WITH TIME ZONE,
  status action,
  updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT r.id, dr.decrypted_report, r.created_at, r.status, r.updated_at
  FROM public.reports r
  JOIN public.decrypted_reports dr ON r.id = dr.report_id
  WHERE r.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.upsert_user_reports(
  p_id UUID,
  p_user_id UUID,
  p_title TEXT,
  p_content TEXT,
  p_created_at TIMESTAMP,
  p_updated_at TIMESTAMP
) RETURNS UUID AS $$

DECLARE
  updated_id UUID;
BEGIN
    INSERT INTO public.reports (id, user_id, title, content, created_at, updated_at)
    VALUES (p_id, p_user_id, p_title, p_content, p_created_at, p_updated_at)
    ON CONFLICT (id) DO UPDATE
    SET title = EXCLUDED.title, content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
    RETURNING id INTO updated_id;
    
    RETURN updated_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.delete_user_report(
  p_user_id UUID,
  p_id UUID
) RETURNS VOID AS $$
BEGIN
  DELETE FROM public.reports 
  WHERE user_id = p_user_id AND id = p_id;
END;
$$ LANGUAGE plpgsql;