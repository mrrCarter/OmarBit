/**
 * IndexedDB cache for match replay data.
 *
 * Per spec: "Replay works offline from IndexedDB after first load."
 * Background sync verifies content hash with server.
 */

const DB_NAME = "omarbit-replay";
const DB_VERSION = 1;
const STORE_NAME = "replays";

export interface ReplayMove {
  ply: number;
  san: string;
  fen: string;
  eval_cp: number | null;
  think_summary: string | null;
  chat_line: string | null;
  timestamp: string;
}

export interface ReplayData {
  match: {
    id: string;
    white_ai_id: string;
    black_ai_id: string;
    time_control: string;
    status: string;
    winner_ai_id: string | null;
    forfeit_reason: string | null;
    pgn: string | null;
    created_at: string;
    completed_at: string | null;
  };
  moves: ReplayMove[];
  content_hash: string;
  move_count: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "match.id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function getCachedReplay(
  matchId: string
): Promise<ReplayData | null> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const request = store.get(matchId);
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(request.error);
    });
  } catch {
    return null;
  }
}

export async function cacheReplay(data: ReplayData): Promise<void> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      store.put(data);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Silently fail — cache is best-effort
  }
}

export async function verifyCacheHash(
  matchId: string,
  serverHash: string
): Promise<boolean> {
  const cached = await getCachedReplay(matchId);
  if (!cached) return false;
  return cached.content_hash === serverHash;
}

export async function clearReplayCache(): Promise<void> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Silently fail
  }
}
