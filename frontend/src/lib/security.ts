/**
 * Security & Sanitization Utilities
 * Defends against XSS, input injection, malicious filenames, and prototype tampering.
 */

// HTML entity escaping for XSS prevention
const ENTITY_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#x27;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;',
};

/**
 * Escapes potentially unsafe HTML characters from untrusted user text.
 */
export function sanitizeText(input: unknown): string {
  if (typeof input !== 'string') {
    return String(input ?? '');
  }
  return input.replace(/[&<>"'`=/]/g, (s) => ENTITY_MAP[s] || s).trim();
}

/**
 * Sanitizes and normalizes filenames to prevent path traversal and null-byte injection.
 * Strips path separators (../, ..\), null bytes, and control characters.
 */
export function sanitizeFilename(filename: string): string {
  if (!filename || typeof filename !== 'string') {
    return 'unnamed_document.txt';
  }

  // Remove null bytes and control chars
  let clean = filename.replace(/[\x00-\x1f\x7f]/g, '');

  // Strip path traversal sequences
  clean = clean.replace(/(\.\.[\/\\])+/g, '');
  clean = clean.replace(/^[/\\]+/, '');

  // Keep only base filename
  const parts = clean.split(/[/\\]/);
  const baseName = parts[parts.length - 1] || 'unnamed_document.txt';

  // Limit filename length to 120 chars
  return baseName.slice(0, 120);
}

/**
 * Validates whether an input query is safe from script injection patterns.
 */
export function validateQueryInput(query: string): { isValid: boolean; sanitized: string; reason?: string } {
  if (typeof query !== 'string') {
    return { isValid: false, sanitized: '', reason: 'Invalid input type.' };
  }

  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return { isValid: false, sanitized: '', reason: 'Query cannot be empty.' };
  }

  if (trimmed.length > 4000) {
    return { isValid: false, sanitized: trimmed.slice(0, 4000), reason: 'Query exceeds maximum allowed length (4000 characters).' };
  }

  // Detect script execution vectors
  const dangerousPatterns = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /data:text\/html/gi,
    /onload\s*=/gi,
    /onerror\s*=/gi,
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(trimmed)) {
      return {
        isValid: false,
        sanitized: sanitizeText(trimmed),
        reason: 'Malicious script pattern detected and rejected.',
      };
    }
  }

  return { isValid: true, sanitized: trimmed };
}

/**
 * Generates a cryptographically secure random token using Web Crypto API.
 */
export function generateSecureToken(byteLength = 32): string {
  const array = new Uint8Array(byteLength);
  window.crypto.getRandomValues(array);
  return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
}
