use crate::cache::DynamoCache;
use crate::SnowflakePool;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{interval, Duration};
use tracing::{info, error, warn};

pub struct CacheProcessor {
    cache: Arc<DynamoCache>,
    snowflake_pool: Arc<Mutex<SnowflakePool>>,
    check_interval_seconds: u64,
}

impl CacheProcessor {
    pub fn new(cache: Arc<DynamoCache>, snowflake_pool: Arc<Mutex<SnowflakePool>>) -> Self {
        let check_interval_seconds = std::env::var("CACHE_CHECK_INTERVAL_SECONDS")
            .unwrap_or_else(|_| "60".to_string())
            .parse()
            .unwrap_or(60);

        Self {
            cache,
            snowflake_pool,
            check_interval_seconds,
        }
    }

    pub async fn start_background_processing(&self) {
        let mut interval = interval(Duration::from_secs(self.check_interval_seconds));
        
        info!(
            target: "cache_processor",
            interval_seconds = self.check_interval_seconds,
            "🔄 Starting cache processor with {}s interval (1 minute)", self.check_interval_seconds
        );

        loop {
            interval.tick().await;
            
            if let Err(e) = self.process_expired_cache().await {
                error!(
                    target: "cache_processor",
                    error = %e,
                    "❌ Error processing expired cache: {}", e
                );
            }
        }
    }

    async fn process_expired_cache(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let start_time = std::time::Instant::now();
        
        // Get expired readings from cache
        let expired_readings = self.cache.get_expired_readings().await?;
        
        if expired_readings.is_empty() {
            return Ok(());
        }

        info!(
            target: "cache_processor",
            expired_count = expired_readings.len(),
            "📦 Processing {} expired cache entries", expired_readings.len()
        );

        // Persist to Snowflake
        let pool_guard = self.snowflake_pool.lock().await;
        let persist_result = pool_guard.batch_insert(&expired_readings).await;
        drop(pool_guard);

        match persist_result {
            Ok(_) => {
                // Successfully persisted, now delete from cache
                if let Err(e) = self.cache.delete_expired_readings(&expired_readings).await {
                    warn!(
                        target: "cache_processor",
                        error = %e,
                        "⚠️ Failed to delete cache entries after successful persistence: {}", e
                    );
                }

                let elapsed = start_time.elapsed();
                info!(
                    target: "cache_processor",
                    processed_count = expired_readings.len(),
                    duration_ms = elapsed.as_millis(),
                    "✅ Successfully processed {} expired cache entries in {:.2?}", 
                    expired_readings.len(), elapsed
                );
            }
            Err(e) => {
                error!(
                    target: "cache_processor",
                    error = %e,
                    failed_count = expired_readings.len(),
                    "❌ Failed to persist {} expired cache entries: {}", 
                    expired_readings.len(), e
                );
                return Err(e);
            }
        }

        Ok(())
    }
}