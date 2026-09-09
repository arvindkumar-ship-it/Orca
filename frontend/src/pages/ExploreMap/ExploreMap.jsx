import "./ExploreMap.css";

const GOOGLE_MAP_EMBED_URL =
  "https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d8846355.07883736!2d79.49626831438127!3d16.365688169143333!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e0!3m2!1sen!2sin!4v1786905621200!5m2!1sen!2sin";

export default function ExploreMap() {
  return (
    <main className="explore-map-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a
          href="/"
          className="breadcrumb-home"
          aria-label="Go back to Home"
        >
          Home
        </a>
        <span className="breadcrumb-separator" aria-hidden="true">
          {"  |  "}
        </span>
        <a
          href="/explore-map"
          className="breadcrumb-current"
          aria-current="page"
          aria-label="Explore Map"
        >
          Map
        </a>
      </nav>

      <section className="map-stage" aria-label="Explore Map">
        <iframe
          className="google-map-embed"
          src={GOOGLE_MAP_EMBED_URL}
          title="Explore Map - India"
          allowFullScreen
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </section>
    </main >
  );
}