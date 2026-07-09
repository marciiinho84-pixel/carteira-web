// Papel & Tinta — textura de papel compartilhada.
// Monta uma vez no layout raiz (não repetir por página).
// 3 camadas absolutas, pointer-events: none, acima do conteúdo e abaixo de modais.
export default function PaperTexture() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-20"
    >
      {/* Grão fino */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22300%22><filter id=%22n%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22/><feColorMatrix type=%22matrix%22 values=%220 0 0 0 0.24 0 0 0 0 0.21 0 0 0 0 0.16 0 0 0 0.16 0%22/></filter><rect width=%22300%22 height=%22300%22 filter=%22url(%23n)%22/></svg>')",
        }}
      />
      {/* Fibras */}
      <div
        className="absolute inset-0 opacity-50"
        style={{
          backgroundImage:
            "url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22420%22 height=%22420%22><filter id=%22f%22><feTurbulence type=%22turbulence%22 baseFrequency=%220.012 0.28%22 numOctaves=%222%22 seed=%227%22/><feColorMatrix type=%22matrix%22 values=%220 0 0 0 0.35 0 0 0 0 0.30 0 0 0 0 0.22 0 0 0 0.05 0%22/></filter><rect width=%22420%22 height=%22420%22 filter=%22url(%23f)%22/></svg>')",
        }}
      />
      {/* Vinheta de luz */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 120% 90% at 38% 18%, rgba(255,252,240,0.28) 0%, rgba(255,252,240,0) 45%, rgba(93,80,58,0.10) 100%)",
        }}
      />
    </div>
  );
}
