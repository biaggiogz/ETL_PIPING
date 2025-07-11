import * as duckdb from '@duckdb/duckdb-wasm';
import { RealTimeReading, LatencyMetrics } from '../types';

class DuckDBService {
  private db: duckdb.AsyncDuckDB | null = null;
  private conn: duckdb.AsyncDuckDBConnection | null = null;
  private insertQueue: RealTimeReading[] = [];
  private insertTimeout: number | null = null;
  private readonly BATCH_INSERT_SIZE = 5;
  private readonly INSERT_INTERVAL_MS = 100;

  async init() {
    const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
    const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);
    const worker = await duckdb.createWorker(bundle.mainWorker!);
    this.db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
    await this.db.instantiate(bundle.mainModule);
    this.conn = await this.db.connect();

    await this.createTables();
  }

  private async createTables() {
    if (!this.conn) return;

    await this.conn.query(`
      CREATE TABLE sensor_readings (
        sensor_id VARCHAR,
        temperature DOUBLE,
        reading_timestamp_ms BIGINT,
        latitude DOUBLE,
        longitude DOUBLE,
        speed_kms DOUBLE,
        connection_speed_mbps DOUBLE,
        kinesis_to_lambda_us BIGINT,
        lambda_processing_us BIGINT,
        cache_to_websocket_us BIGINT,
        websocket_to_frontend_us BIGINT,
        total_pipeline_us BIGINT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await this.conn.query(`
      CREATE TABLE latency_metrics (
        kinesis_to_lambda_us BIGINT,
        lambda_processing_us BIGINT,
        cache_to_websocket_us BIGINT,
        websocket_to_frontend_us BIGINT,
        total_pipeline_us BIGINT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  async insertReading(reading: RealTimeReading) {
    this.insertQueue.push(reading);
    
    if (this.insertQueue.length >= this.BATCH_INSERT_SIZE) {
      await this.flushInserts();
    } else if (!this.insertTimeout) {
      this.insertTimeout = window.setTimeout(() => this.flushInserts(), this.INSERT_INTERVAL_MS);
    }
  }

  private async flushInserts() {
    if (!this.conn || this.insertQueue.length === 0) return;
    
    const readings = this.insertQueue.splice(0);
    
    if (this.insertTimeout) {
      clearTimeout(this.insertTimeout);
      this.insertTimeout = null;
    }

    try {
      const values = readings.map(r => 
        `('${r.sensor_id}',${r.temperature},${r.reading_timestamp_ms},${r.position.latitude},${r.position.longitude},${r.speed_kms},${r.connection_speed_mbps},${r.kinesis_to_lambda_us},${r.lambda_processing_us},${r.cache_to_websocket_us},${r.websocket_to_frontend_us},${r.total_pipeline_us},CURRENT_TIMESTAMP)`
      ).join(',');
      
      await this.conn.query(`INSERT INTO sensor_readings VALUES ${values}`);
      
      const latencyValues = readings.map(r => 
        `(${r.kinesis_to_lambda_us},${r.lambda_processing_us},${r.cache_to_websocket_us},${r.websocket_to_frontend_us},${r.total_pipeline_us},CURRENT_TIMESTAMP)`
      ).join(',');
      
      await this.conn.query(`INSERT INTO latency_metrics VALUES ${latencyValues}`);
    } catch (error) {
      console.error('Batch insert error:', error);
    }
  }

  async getLatestReadings(): Promise<RealTimeReading[]> {
    if (!this.conn) return [];

    const result = await this.conn.query(`
      SELECT DISTINCT ON (sensor_id) *
      FROM sensor_readings
      ORDER BY sensor_id, timestamp DESC
    `);

    return result.toArray().map(row => ({
      sensor_id: row.sensor_id,
      temperature: row.temperature,
      reading_timestamp_ns: BigInt(row.reading_timestamp_ms * 1000000),
      reading_timestamp_us: row.reading_timestamp_ms * 1000,
      reading_timestamp_ms: row.reading_timestamp_ms,
      position: { latitude: row.latitude, longitude: row.longitude },
      speed_kms: row.speed_kms,
      connection_speed_mbps: row.connection_speed_mbps,
      cache_timestamp_ns: BigInt(0),
      notification_timestamp_ns: BigInt(0),
      cache_to_notification_latency_ns: 0,
      cache_to_notification_latency_us: 0,
      cache_to_websocket_us: row.cache_to_websocket_us,
      kinesis_to_lambda_us: row.kinesis_to_lambda_us,
      lambda_processing_us: row.lambda_processing_us,
      total_pipeline_us: row.total_pipeline_us,
      websocket_to_frontend_us: row.websocket_to_frontend_us,
      pipeline_tracking: true,
      type: 'real_time_reading'
    }));
  }

  async getLatencyMetrics(): Promise<LatencyMetrics[]> {
    if (!this.conn) return [];

    const result = await this.conn.query(`
      SELECT * FROM latency_metrics
      ORDER BY timestamp DESC
      LIMIT 50
    `);

    return result.toArray().map(row => ({
      kinesis_to_lambda_us: row.kinesis_to_lambda_us,
      lambda_processing_us: row.lambda_processing_us,
      cache_to_websocket_us: row.cache_to_websocket_us,
      websocket_to_frontend_us: row.websocket_to_frontend_us,
      total_pipeline_us: row.total_pipeline_us,
      timestamp: new Date(row.timestamp).getTime()
    }));
  }

  async cleanup() {
    if (!this.conn) return;
    
    try {
      await this.conn.query(`DELETE FROM sensor_readings WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '30 minutes'`);
      await this.conn.query(`DELETE FROM latency_metrics WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '30 minutes'`);
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  }
}

export const duckDBService = new DuckDBService();