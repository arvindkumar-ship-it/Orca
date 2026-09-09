const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `Request failed with status ${response.status}`;

    throw new Error(
      Array.isArray(message)
        ? message.map((item) => item.msg || JSON.stringify(item)).join(", ")
        : String(message)
    );
  }

  return data;
}

export async function requestOtp(phone) {
  return request("/v1/auth/otp/request", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function verifyOtp(phone, code) {
  return request("/v1/auth/otp/verify", {
    method: "POST",
    body: JSON.stringify({ phone, code }),
  });
}

export async function logout() {
  const token = localStorage.getItem("wavesafe.access_token");

  if (!token) {
    clearAuthSession();
    return null;
  }

  try {
    return await request("/v1/auth/logout", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    });
  } finally {
    clearAuthSession();
  }
}

export function saveAuthSession({ access_token, token_type, user_id }) {
  localStorage.setItem("wavesafe.access_token", access_token);
  localStorage.setItem(
    "wavesafe.auth",
    JSON.stringify({
      token_type: token_type || "bearer",
      user_id,
    })
  );
}

export function getAuthSession() {
  try {
    const raw = localStorage.getItem("wavesafe.auth");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearAuthSession() {
  localStorage.removeItem("wavesafe.access_token");
  localStorage.removeItem("wavesafe.auth");
}
