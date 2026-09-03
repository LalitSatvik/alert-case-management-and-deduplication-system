import { QueryClient } from "@tanstack/react-query";

/**
 * The app-wide React Query client. Exported as a module singleton (not created
 * inside `main.tsx`) so non-component code — e.g. `logout()` in AuthContext —
 * can clear the cache without threading it through a hook or provider.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 15_000 },
  },
});
