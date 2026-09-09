import { useEffect, useMemo, useRef, useState } from "react";
import { logout } from "../services/auth";
import "./landing.css";

export default function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchRef = useRef(null);

  const searchItems = useMemo(() => [
    { label: "Home", keywords: "home landing", href: "/" },
    { label: "Explore Map", keywords: "map explore location", href: "/explore-map" },
    { label: "Trip Planner", keywords: "trip planner travel plan your trip", href: "/trip-planning" },
    { label: "SOS", keywords: "sos emergency", href: "/sos" },
    { label: "Beaches", keywords: "beaches beach destinations", href: "/beaches" },
    { label: "Profile", keywords: "profile account user", href: "/profile" },
    { label: "Goa", keywords: "goa beach", href: "/beaches?state=goa" },
    { label: "Maharashtra", keywords: "maharashtra beach", href: "/beaches?state=maharashtra" },
    { label: "Gujarat", keywords: "gujarat beach", href: "/beaches?state=gujarat" },
    { label: "Karnataka", keywords: "karnataka beach", href: "/beaches?state=karnataka" },
    { label: "Kerala", keywords: "kerala beach", href: "/beaches?state=kerela" },
    { label: "Tamil Nadu", keywords: "tamil nadu beach", href: "/beaches?state=tamil-nadu" },
    { label: "Andhra Pradesh", keywords: "andhra pradesh beach", href: "/beaches?state=andhra-pradesh" },
    { label: "Odisha", keywords: "odisha beach", href: "/beaches?state=odisha" },
    { label: "West Bengal", keywords: "west bengal beach", href: "/beaches?state=west-bengal" },
  ], []);

  const searchResults = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return [];
    return searchItems
      .filter((item) => `${item.label} ${item.keywords}`.includes(query))
      .slice(0, 6);
  }, [searchItems, searchQuery]);
  const menuButtonRef = useRef(null);
  const sideMenuRef = useRef(null);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        menuOpen &&
        sideMenuRef.current &&
        !sideMenuRef.current.contains(event.target) &&
        menuButtonRef.current &&
        !menuButtonRef.current.contains(event.target)
      ) {
        setMenuOpen(false);
      }
    };

    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  return (
    <main className="page">
      <section id="home" className="coastal-top">
        <video
          className="coastal-video"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          aria-hidden="true"
        >
          <source src="/assets/waves.mp4" type="video/mp4" />
          Your browser does not support the HTML5 video element.
        </video>

        <div className="coastal-video-overlay" aria-hidden="true" />

        <div
          className={`side-menu${menuOpen ? " open" : ""}`}
          id="sideMenu"
          ref={sideMenuRef}
        >
          <a href="#home" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">⌂</span><span>Home</span>
          </a>
          <a href="/explore-map" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">▱</span><span>Explore Map</span>
          </a>
          <a href="/your-trips" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">▣</span><span>Trip Planner</span>
          </a>
          <a href="/sos" className="side-menu-item sos-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">♒</span><span>SOS</span>
          </a>
          <a href="#safe-zones" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">✤</span><span>Safe Zones</span>
          </a>
          <a href="/chat" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">💬</span><span>Ask ORCA</span>
          </a>
          <a href="/profile" className="side-menu-item" onClick={closeMenu}>
            <span className="menu-item-icon">♙</span><span>Profile</span>
          </a>
        </div>

        <header className="nav">
          <nav className="nav-links" aria-label="Primary navigation">
            <a href="#home" className="nav-link active">Home</a>
            <a href="/explore-map" className="nav-link">Map</a>
            <a href="/chat" className="nav-link">Ask ORCA</a>
            <a href="/sos" className="nav-link sos-nav">SOS</a>
            <a href="/beaches" className="nav-link">Beaches</a>
          </nav>

          <div className="nav-tools">
            <button
              type="button"
              className="login"
              onClick={async () => {
                try { await logout(); } catch { }
                window.location.assign("/signup");
              }}
            >
              Logout
            </button>

            <div className="search" ref={searchRef}>
              <input
                className="search-input"
                type="search"
                value={searchQuery}
                placeholder="Search here"
                aria-label="Search WaveSafe"
                autoComplete="off"
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && searchResults[0]) {
                    window.location.assign(searchResults[0].href);
                  }
                  if (event.key === "Escape") {
                    setSearchQuery("");
                  }
                }}
              />
              <span className="search-icon" aria-hidden="true" />

              {searchQuery.trim() && (
                <div className="search-results" role="listbox" aria-label="Search results">
                  {searchResults.length ? (
                    searchResults.map((result) => (
                      <a
                        key={`${result.label}-${result.href}`}
                        href={result.href}
                        className="search-result"
                        role="option"
                      >
                        {result.label}
                      </a>
                    ))
                  ) : (
                    <div className="search-no-result">No results found</div>
                  )}
                </div>
              )}
            </div>

            <button
              className="nav-round-btn"
              id="menuToggle"
              ref={menuButtonRef}
              type="button"
              aria-label="Open navigation menu"
              aria-expanded={menuOpen}
              onClick={(event) => {
                event.stopPropagation();
                setMenuOpen((value) => !value);
              }}
            >
              <img src="/assets/menu.png" alt="" />
            </button>
          </div>
        </header>

        <div className="brand">WaveSafe</div>

        <div className="hero">
          <div className="hero-copy">
            <a href="/beaches" className="hero-title-link" aria-label="Explore the Indian beaches">
              <h1 className="hero-title">Explore the Indian beaches</h1>
            </a>
            <button
              id="trip-planner"
              type="button"
              className="hero-script hero-trip-link"
              onClick={() => window.location.assign("/your-trips")}
            >
              Plan your trip
            </button>
          </div>
        </div>

        <section id="destinations" className="destinations">
          <h2 className="section-title">DESTINATIONS</h2>

          <div className="dest-grid">
            <a href="/beaches" className="dest-card" aria-label="Explore this destination">
              <img src="/assets/goa.jpg" alt="Goa coast" />
              <span className="dest-name">GOA</span>
            </a>
            <a href="/beaches" className="dest-card" aria-label="Explore this destination">
              <img src="/assets/odisha.jpg" alt="Odisha coast" />
              <span className="dest-name">Odisha</span>
            </a>
            <a href="/beaches" className="dest-card" aria-label="Explore this destination">
              <img src="/assets/kerala.jpg" alt="Kerala coast" />
              <span className="dest-name">Kerela</span>
            </a>
            <a href="/beaches" className="dest-card" aria-label="Explore this destination">
              <img src="/assets/gujarat.jpg" alt="Gujarat coast" />
              <span className="dest-name">Gujarat</span>
            </a>
            <a href="/beaches" className="dest-card" aria-label="Explore this destination">
              <img src="/assets/mumbai.jpg" alt="Mumbai coast" />
              <span className="dest-name">Mumbai</span>
            </a>
          </div>
        </section>

        <section className="features" aria-label="WaveSafe features">
          <div className="features-track">
            <div className="feature">Real time safety</div>
            <div className="feature">Smart alerts</div>
            <div className="feature">Trip Planner</div>
            <div className="feature">One tap SOS</div>
            {/* <div className="feature">Real time safety</div> */}

            <div className="feature" aria-hidden="true">Real time safety</div>
            <div className="feature" aria-hidden="true">Smart alerts</div>
            <div className="feature" aria-hidden="true">Trip Planner</div>
            <div className="feature" aria-hidden="true">One tap SOS</div>
            {/*<div className="feature" aria-hidden="true">Real time safety</div>*/}
          </div>
        </section>

        <section id="map" className="explore">
          <img
            className="explore-map-bg"
            src="/assets/old_map.jpg"
            alt="Vintage map of India"
          />

          <div className="explore-heading">
            <div className="heading-rule" />
            <div className="heading-rule right" />
            <p className="eyebrow">Explore India’s</p>
            <div className="mega">
              COASTAL<br />
              PARADISE
            </div>
          </div>

          <div className="map-shell">
            <div className="map-frame">
              <iframe
                title="Google Maps — India"
                loading="lazy"
                allowFullScreen
                src="https://www.google.com/maps?q=India&output=embed"
              />
            </div>
            <a className="map-note map-note-link" href="/explore-map">
              Interactive Google Map — zoom and pan to explore India’s coastline.
            </a>
          </div>
        </section>

        <section id="emergency" className="emergency">
          <div className="emergency-question">Is Emergency ?</div>
          <button
            className="emergency-btn"
            type="button"
            onClick={() => window.location.assign("/sos")}
          >
            Press SOS
          </button>

          <a
            href="#"
            className="whatsapp-btn"
            aria-label="Contact us on WhatsApp"
            onClick={(event) => event.preventDefault()}
          >
            <img src="/assets/whatsapp.svg" alt="WhatsApp" />
          </a>
        </section>

        <footer className="footer">
          <div>
            <div className="footer-brand">WaveSafe</div>
            <div className="footer-desc">
              Your trusted companion for beach safety,<br />
              trip planning, and real-time coastal insights.
            </div>
          </div>

          <div className="footer-col">
            <h3>Quick links</h3>
            <a href="#home">Home</a>
            <a href="#destinations">Menu</a>
            <a href="/explore-map">Map</a>
            <a href="/chat">Ask ORCA</a>
            <a href="/your-trips">Trip Planner</a>
            <a href="/beaches">Beaches</a>
          </div>

          <div className="footer-col">
            <h3>Services</h3>
            <a href="#safe-zones">Safety Overview</a>
            <a href="#weather">Weather Forecast</a>
            <a href="#safe-zones">Safe Zones</a>
            <a href="/sos">Emergency SOS</a>
            <a href="#safe-zones">Nearby Services</a>
          </div>

          <div className="footer-col">
            <h3>Support</h3>
            <a href="#help">Help Center</a>
            <a href="#contact">Contact Us</a>
            <a href="#faq">FAQ</a>
            <a href="#privacy">Privacy Policy</a>
            <a href="#terms">Terms &amp; Conditions</a>
          </div>

          <div className="footer-col">
            <h3>Follow us</h3>
            <a href="#facebook" onClick={(e) => e.preventDefault()}>Facebook</a>
            <a href="#instagram" onClick={(e) => e.preventDefault()}>Instagram</a>
            <a href="#whatsapp" onClick={(e) => e.preventDefault()}>WhatsApp</a>
          </div>
        </footer>
      </section>
    </main>
  );
}