import { useState } from "react";

const MODES = {
  login: {
    title: "Log in",
    submit: "Log in",
    switchText: "No account yet? Sign up",
  },
  register: {
    title: "Sign up",
    submit: "Create account",
    switchText: "Have an account? Log in",
  },
};

const INPUT =
  "w-full rounded-md bg-card px-3 py-2 type-body text-ink outline-2 outline-transparent focus:outline-accent/40";

function LoginPage({ auth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const texts = MODES[mode];

  function handleSubmit(event) {
    event.preventDefault();
    auth.submit(mode, email, password);
  }

  function switchMode() {
    setMode(mode === "login" ? "register" : "login");
    auth.clearError();
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm flex flex-col gap-3"
      >
        <h1 className="type-title text-ink">{texts.title}</h1>
        <label className="flex flex-col gap-1 type-label text-ink">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={INPUT}
          />
        </label>
        <label className="flex flex-col gap-1 type-label text-ink">
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={INPUT}
          />
        </label>
        {auth.error && <p className="type-caption text-warn">{auth.error}</p>}
        <button
          type="submit"
          disabled={auth.isSubmitting}
          className="btn-primary justify-center"
        >
          {auth.isSubmitting ? "Please wait..." : texts.submit}
        </button>
        <button
          type="button"
          onClick={switchMode}
          className="type-caption text-muted hover:text-ink"
        >
          {texts.switchText}
        </button>
      </form>
    </main>
  );
}

export default LoginPage;
