/** Match Ollama model names (with optional :latest tag). */
function modelAliases(name: string): Set<string> {
  const trimmed = name.trim();
  if (!trimmed) return new Set();
  const aliases = new Set([trimmed]);
  if (!trimmed.includes(":")) {
    aliases.add(`${trimmed}:latest`);
  } else if (trimmed.endsWith(":latest")) {
    aliases.add(trimmed.slice(0, -":latest".length));
  }
  return aliases;
}

export function ollamaModelInstalled(requested: string, installed: string[]): boolean {
  if (!requested) return false;
  const req = modelAliases(requested);
  return installed.some((name) => {
    for (const alias of modelAliases(name)) {
      if (req.has(alias)) return true;
    }
    return false;
  });
}
