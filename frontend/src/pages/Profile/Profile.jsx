import { useMemo } from "react";
import { clearAuthSession, getAuthSession, logout } from "../../services/auth";
import "./Profile.css";

function getStoredProfile() {
  try {
    const session = getAuthSession();

    if (!session?.user_id) {
      return {
        userId: "",
        fullName: "WaveSafe User",
        phone: "",
      };
    }

    const raw = localStorage.getItem(`wavesafe.user.${session.user_id}`);
    const linked = raw ? JSON.parse(raw) : {};

    return {
      userId: session.user_id,
      fullName: linked.fullName || "WaveSafe User",
      phone: linked.phone || "",
    };
  } catch {
    return {
      userId: "",
      fullName: "WaveSafe User",
      phone: "",
    };
  }
}

function ProfileMenuRow({ href, icon, iconClass = "", children, inlineIcon = false }) {
  return (
    <a href={href} className="profile-menu-row">
      <span className="menu-icon-box">
        {inlineIcon ? (
          <svg
            className={`menu-icon ${iconClass}`}
            width="35"
            height="38"
            viewBox="0 0 35 38"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M17.4998 4.35414C18.8319 4.35146 20.1348 4.77773 21.2438 5.57903C22.3528 6.38033 23.2181 7.52067 23.7301 8.85586C24.2422 10.1911 24.3781 11.6611 24.1206 13.0802C23.8632 14.4992 23.2239 15.8035 22.2837 16.8281C21.3435 17.8527 20.1446 18.5516 18.8385 18.8364C17.5325 19.1212 16.178 18.9791 14.9463 18.4281C13.7146 17.8771 12.6611 16.9419 11.9189 15.7409C11.1768 14.5398 10.7793 13.1268 10.7769 11.6805V11.6668C10.7769 9.72974 11.4848 7.87177 12.7452 6.50076C14.0056 5.12975 15.7156 4.35772 17.4998 4.35414Z"
              stroke="black"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M17.5002 21.6895C25.0258 21.6895 30.9585 27.1303 30.9585 29.8402V33.6458H4.04199V29.7721C4.04199 27.0622 9.97464 21.6895 17.5002 21.6895Z"
              stroke="black"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <img className={`menu-icon ${iconClass}`} src={icon} alt="" />
        )}
      </span>
      <span className="menu-label">{children}</span>
      <img className="menu-arrow" src="/assets/Vector-1.svg" alt="" />
    </a>
  );
}

export default function Profile() {
  const profile = useMemo(() => getStoredProfile(), []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Even if the backend logout endpoint fails, remove the local token
      // so the protected frontend cannot remain open.
    } finally {
      clearAuthSession();
      window.location.assign("/signup");
    }
  };

  return (
    <main className="profile-page">
      <nav className="profile-breadcrumb" aria-label="Breadcrumb">
        <a href="/" className="profile-breadcrumb-link">Home</a>
        <span className="profile-breadcrumb-separator" aria-hidden="true">|</span>
        <span className="profile-breadcrumb-current" aria-current="page">Profile</span>
      </nav>
      <section className="profile-card">
        <div className="profile-avatar">
          <div className="profile-avatar-placeholder">
            <img src="/assets/contacts_alt logo.svg" alt="" />
          </div>
        </div>

        <div className="profile-info">
          <div className="profile-name">{profile.fullName}</div>
          <div className="profile-detail shadow">
            {profile.phone || "Phone number not available"}
          </div>
        </div>

        <button className="logout-btn" type="button" onClick={handleLogout}>
          Log Out
        </button>
      </section>

      <section className="profile-menu-card">
        <ProfileMenuRow href="/your-trips" icon="/assets/Vector.svg" iconClass="trips">
          My Trips
        </ProfileMenuRow>

        <ProfileMenuRow href="#saved-beaches" icon="/assets/Group 20.svg" iconClass="beaches">
          Saved Beaches
        </ProfileMenuRow>

        <ProfileMenuRow
          href="#emergency-contact"
          iconClass="emergency"
          inlineIcon
        >
          Emergency Contact
        </ProfileMenuRow>

        <ProfileMenuRow
          href="#settings"
          icon="/assets/Vector-2.svg"
          iconClass="settings"
        >
          Setting
        </ProfileMenuRow>

        <ProfileMenuRow href="#help-support" icon="/assets/a.svg" iconClass="help">
          Help &amp; Support
        </ProfileMenuRow>
      </section>
    </main>
  );
}