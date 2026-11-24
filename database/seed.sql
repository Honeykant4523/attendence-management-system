USE smartattend;
-- Reference records only. Create the first administrator through POST /api/auth/register
-- so its password is securely hashed by the application.
INSERT INTO departments (name, code) VALUES
  ('Engineering', 'ENG'), ('Human Resources', 'HR'), ('Operations', 'OPS')
ON DUPLICATE KEY UPDATE name = VALUES(name);
INSERT INTO designations (title) VALUES
  ('Software Engineer'), ('HR Manager'), ('Operations Executive')
ON DUPLICATE KEY UPDATE title = VALUES(title);
INSERT INTO shifts (name, start_time, end_time, grace_minutes, full_day_minutes, half_day_minutes, overtime_after_minutes) VALUES
  ('General Shift', '09:00:00', '18:00:00', 10, 480, 240, 480)
ON DUPLICATE KEY UPDATE name = VALUES(name);
