// src/utils/guardrails.js

const BLOCKED_PATTERNS = [
  /ignore previous instructions/i,
  /reveal system prompt/i,
  /you are now a/i,
  /disregard all rules/i,
  /bypass safety/i
];

/**
 * Client-side pre-screen for obvious prompt injections.
 * Returns true if safe, false if blocked.
 */
export function clientSideGuardrail(input) {
  if (!input || typeof input !== "string") return false;

  // 1. Check length constraints (e.g., max 1000 characters)
  if (input.length > 1000) {
    return { isSafe: false, reason: "Query is too long." };
  }

  // 2. Check against known malicious regex patterns
  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(input)) {
      return { 
        isSafe: false, 
        reason: "🛡️ Intercepted by client guardrail: Potentially unsafe prompt pattern detected." 
      };
    }
  }

  return { isSafe: true };
}