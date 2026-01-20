import sqlite3 from 'sqlite3'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const dbPath = path.resolve(process.cwd(), 'data/do-tools.db')

console.log('Using database:', dbPath)

const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message)
    process.exit(1)
  }
  console.log('Connected to the database.')
})

const createTableSQL = `
CREATE TABLE IF NOT EXISTS funds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  userId INTEGER NOT NULL,
  fundCode VARCHAR(255) NOT NULL,
  fundName VARCHAR(255) NOT NULL,
  fundType VARCHAR(255),
  style VARCHAR(255),
  focusBoards TEXT,
  scheduleEnabled BOOLEAN DEFAULT 0,
  scheduleTime VARCHAR(255),
  scheduleInterval VARCHAR(255) DEFAULT '24H',
  createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (userId) REFERENCES users(id)
);
`

db.serialize(() => {
  db.run(createTableSQL, (err) => {
    if (err) {
      console.error('[FAIL] Create funds table:', err.message)
    } else {
      console.log('[OK] Created funds table')
    }
  })
})

db.close((err) => {
  if (err) {
    console.error('Error closing database:', err.message)
  } else {
    console.log('Database connection closed.')
  }
})
