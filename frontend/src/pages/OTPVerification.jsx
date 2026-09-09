import { useEffect, useRef, useState } from "react";
import { requestOtp, saveAuthSession, verifyOtp } from "../services/auth";
import "./otp-verification.css";

const OTP_LENGTH = 6;
const DEFAULT_PHONE = "8090559340";

function getSignupData() {
  try {
    const saved = sessionStorage.getItem("wavesafe.signup");
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

export default function OTPVerification() {
  const [digits, setDigits] = useState(Array(OTP_LENGTH).fill(""));
  const [phone, setPhone] = useState(DEFAULT_PHONE);
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const inputRefs = useRef([]);

  useEffect(() => {
    const signupData = getSignupData();

    if (signupData?.phone) {
      setPhone(signupData.phone);
    }

    if (signupData?.fullName) {
      setFullName(signupData.fullName);
    }
  }, []);

  const updateDigit = (index, value) => {
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = digit;
    setDigits(next);
    setError("");

    if (digit && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, event) => {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }

    if (event.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }

    if (event.key === "ArrowRight" && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (event) => {
    const pasted = event.clipboardData
      .getData("text")
      .replace(/\D/g, "")
      .slice(0, OTP_LENGTH);

    if (!pasted) return;

    event.preventDefault();

    const next = Array(OTP_LENGTH).fill("");
    pasted.split("").forEach((digit, index) => {
      next[index] = digit;
    });

    setDigits(next);
    setError("");

    const focusIndex = Math.min(pasted.length, OTP_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
  };

  const handleVerify = async () => {
    const code = digits.join("");

    if (code.length !== OTP_LENGTH || loading) {
      setError("Please enter the complete verification code.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      // Backend contract:
      // POST /v1/auth/otp/verify
      // Body: { phone, code }
      // Response: { access_token, token_type, user_id }
      const result = await verifyOtp(phone, code);

      saveAuthSession({
        access_token: result.access_token,
        token_type: result.token_type,
        user_id: result.user_id,
      });

      // The backend currently returns user_id but the auth contract does
      // not accept full_name. Keep the supplied name linked to that backend
      // user_id on the frontend until a backend profile/name endpoint exists.
      localStorage.setItem(
        `wavesafe.user.${result.user_id}`,
        JSON.stringify({
          user_id: result.user_id,
          fullName,
          phone,
        })
      );

      sessionStorage.removeItem("wavesafe.signup");

      // Auth token is now verified. Enter the protected landing/home page.
      window.location.assign("/");
    } catch (verifyError) {
      setError(verifyError.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resending || loading) return;

    setError("");
    setResending(true);

    try {
      // Backend contract: POST /v1/auth/otp/request
      await requestOtp(phone);
      setDigits(Array(OTP_LENGTH).fill(""));
      inputRefs.current[0]?.focus();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setResending(false);
    }
  };

  return (
    <main className="otp-page">
      <section className="otp-canvas" aria-labelledby="otp-title">
        <h1 id="otp-title" className="otp-title">
          Verify your number
        </h1>

        <p className="otp-description">
          Please enter the verification code we sent to
        </p>

        <p className="otp-number">{phone}</p>

        <div className="otp-inputs" role="group" aria-label="Verification code">
          {digits.map((digit, index) => (
            <input
              key={index}
              ref={(element) => {
                inputRefs.current[index] = element;
              }}
              className="otp-input"
              type="text"
              inputMode="numeric"
              autoComplete={index === 0 ? "one-time-code" : "off"}
              maxLength={1}
              value={digit}
              aria-label={`Verification digit ${index + 1}`}
              onChange={(event) => updateDigit(index, event.target.value)}
              onKeyDown={(event) => handleKeyDown(index, event)}
              onPaste={handlePaste}
              disabled={loading || resending}
            />
          ))}
        </div>

        <button
          className="otp-continue"
          type="button"
          onClick={handleVerify}
          disabled={loading}
        >
          {loading ? "Verifying..." : "Continue"}
        </button>

        <p className="otp-resend">
          <span>Didn’t receive the code ? </span>
          <button
            className="otp-resend-strong"
            type="button"
            onClick={handleResend}
            disabled={resending || loading}
          >
            {resending ? "Sending..." : "Resend "}
          </button>
        </p>

        {error ? (
          <p className="otp-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  );
}