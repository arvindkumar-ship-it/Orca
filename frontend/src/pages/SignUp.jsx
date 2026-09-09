import { useState } from "react";
import { requestOtp } from "../services/auth";
import "./sign-up.css";

export default function SignUp() {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const cleanName = fullName.trim();
    const cleanPhone = phone.trim();

    if (!cleanName || !cleanPhone || loading) return;

    setError("");
    setLoading(true);

    try {
      // Backend contract: POST /v1/auth/otp/request
      // Body: { phone }
      await requestOtp(cleanPhone);

      // Full name is carried forward because the current OTP request
      // contract accepts phone only.
      sessionStorage.setItem(
        "wavesafe.signup",
        JSON.stringify({
          fullName: cleanName,
          phone: cleanPhone,
        })
      );

      window.location.assign("/otp");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="signup-page">
      <div className="signup-canvas">
        <div className="signup-content">
          <header className="signup-header">
            <h1 id="signup-title">Sign Up</h1>
            <p>Create an account to get started</p>
          </header>

          <form
            className="signup-form"
            aria-labelledby="signup-title"
            onSubmit={handleSubmit}
          >
            <label className="sr-only" htmlFor="full-name">
              Full Name
            </label>
            <input
              id="full-name"
              name="fullName"
              type="text"
              autoComplete="name"
              placeholder="Full Name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              disabled={loading}
            />

            <label className="sr-only" htmlFor="phone-number">
              Phone number
            </label>
            <input
              id="phone-number"
              name="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="Phone number"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              required
              disabled={loading}
            />

            <button type="submit" disabled={loading}>
              {loading ? "Sending..." : "Continue"}
            </button>

            {error ? (
              <p className="signup-error" role="alert">
                {error}
              </p>
            ) : null}
          </form>
        </div>
      </div>
    </main>
  );
}