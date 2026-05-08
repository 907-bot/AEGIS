import fs from 'fs';
import path from 'path';
import { Pool } from 'pg';
import dotenv from 'dotenv';

dotenv.config({ path: path.join(__dirname, '../../../../.env') });

async function migrate() {
  const connectionString = process.env.DATABASE_URL;
  
  if (!connectionString) {
    console.error('❌ DATABASE_URL is not set');
    process.exit(1);
  }

  console.log('🚀 Starting database migration...');

  const pool = new Pool({
    connectionString,
    ssl: connectionString.includes('neon.tech') || process.env.NODE_ENV === 'production'
      ? { rejectUnauthorized: false }
      : false
  });

  try {
    const schemaPath = path.join(__dirname, 'schema.sql');
    const schema = fs.readFileSync(schemaPath, 'utf8');

    console.log('⏳ Executing schema.sql...');
    await pool.query(schema);
    
    console.log('✅ Migration successful');
  } catch (err) {
    console.error('❌ Migration failed:', err);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

migrate();
