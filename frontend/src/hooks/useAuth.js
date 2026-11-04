import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useAuth() {
  const [user, setUser] = useState(undefined); // undefined: checking, null: logged out
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  // mode is "login" or "register"; both log in on success.
  async function submit(mode, email, password) {
    setError(null);
    setIsSubmitting(true);
    try {
      const loggedIn = await fetchJson(`/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      setUser(loggedIn);
    } catch (error) {
      setError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function logout() {
    try {
      await fetchJson("/auth/logout", { method: "POST" });
    } catch (error) {
      console.error("Error while logging out: ", error);
    }
    setUser(null);
  }

  return {
    user,
    submit,
    logout,
    isSubmitting,
    error,
    clearError: () => setError(null),
  };
}
