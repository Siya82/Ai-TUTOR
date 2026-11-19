/*
 * NEW 19 Nov 2026 (ADR-040, THUTOra brand specs). The product wordmark:
 * a product mark, "THUTO" in the base colour (white on the app's navy
 * background, where navy text wouldn't show), "ra" in the product's accent
 * colour, and the product name in the product colour.
 */
const MARKS = {
  learn: "/thutora-learn-logo.png",
  teach: "/thutora-teach-logo.png",
  connect: "/thutora-connect-logo.png",
  insights: "/thutora-insights-logo.png",
  admin: "/thutora-admin-logo.png", // ADR-044
};

export default function Wordmark({ product, showProduct = true, size = "md" }) {
  return (
    <div className={`wordmark wordmark--${size}`} data-product={product}>
      <img src={MARKS[product]} alt="" className="wordmark__mark" />
      <span className="wordmark__text" aria-label={`THUTOra ${showProduct ? product.toUpperCase() : ""}`.trim()}>
        <span className="wordmark__thuto">THUTO</span>
        <span className="wordmark__ra">ra</span>
      </span>
      {showProduct && <span className="product-badge">{product.toUpperCase()}</span>}
    </div>
  );
}
