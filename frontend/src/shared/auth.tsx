import { useQuery } from "@tanstack/react-query";

import { fetchMe } from "./api";
import type { CurrentUser } from "./types";

/**
 * Текущий пользователь. Запрос /auth/me/ кэшируется под ключом ["me"];
 * при 401/403 (не залогинен) query переходит в isError → user === null.
 */
export function useAuth() {
  const q = useQuery<CurrentUser>({
    queryKey: ["me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: Infinity,
  });
  return {
    user: q.data ?? null,
    isLoading: q.isLoading,
    isError: q.isError,
    refetch: q.refetch,
  };
}
