import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const ADMIN_AUTH_FILE = path.join(__dirname, '..', '.auth', 'admin.json');
export const ADMIN_MARKER_FILE = path.join(__dirname, '..', '.auth', 'admin-token-marker.json');
