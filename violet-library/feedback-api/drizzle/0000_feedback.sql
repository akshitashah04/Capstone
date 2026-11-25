CREATE TABLE `feedback` (
  `id` text PRIMARY KEY NOT NULL,
  `payload_digest` text NOT NULL,
  `query_text` text NOT NULL,
  `results_json` text NOT NULL,
  `target_book_id` text,
  `rating` text NOT NULL CHECK (`rating` IN ('useful', 'partial', 'not_useful', 'none_fit')),
  `reason` text,
  `model_key` text NOT NULL,
  `search_mode` text NOT NULL,
  `release_id` text NOT NULL,
  `catalog_sha` text NOT NULL,
  `ip_hash` text NOT NULL,
  `created_at` integer NOT NULL,
  `updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `feedback_created_at_idx` ON `feedback` (`created_at`);
--> statement-breakpoint
CREATE TABLE `feedback_events` (
  `id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  `feedback_id` text NOT NULL,
  `action` text NOT NULL,
  `rating` text,
  `reason` text,
  `created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `feedback_events_feedback_id_idx` ON `feedback_events` (`feedback_id`);
--> statement-breakpoint
CREATE TABLE `rate_counters` (
  `key` text PRIMARY KEY NOT NULL,
  `count` integer NOT NULL,
  `updated_at` integer NOT NULL
);
