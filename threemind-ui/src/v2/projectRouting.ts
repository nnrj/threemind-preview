import {
  useSearchParams,
  createSearchParams,
  type SetURLSearchParams,
} from "react-router-dom";

// Resource ownership stays in a deep link when an editor changes its filters.
export function useProjectSearchParams(): ReturnType<typeof useSearchParams> {
  const [params, setParams] = useSearchParams();
  const set: SetURLSearchParams = (next, options) =>
    setParams((previous) => {
      const value = createSearchParams(
        typeof next === "function" ? next(previous) : next,
      );
      const owner = previous.get("project");
      if (owner && !value.has("project")) value.set("project", owner);
      if (previous.get("action") === "manage" && !value.has("action"))
        value.set("action", "manage");
      return value;
    }, options);
  return [params, set];
}
