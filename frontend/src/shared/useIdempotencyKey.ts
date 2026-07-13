import { useCallback, useState } from "react";

import { createClientUuid } from "./uuid";

/**
 * Ключ идемпотентности на жизненный цикл документа (чек, приёмка).
 *
 * - `key` стабилен между рендерами и повторными отправками: повторный клик,
 *   retry после таймаута или повторная отправка того же документа используют
 *   тот же UUID.
 * - `renew()` создаёт НОВЫЙ ключ — вызывать только после подтверждённого успеха
 *   или явного сброса/создания нового документа.
 */
export function useIdempotencyKey() {
  const [key, setKey] = useState(() => createClientUuid());
  const renew = useCallback(() => setKey(createClientUuid()), []);
  return { key, renew };
}
