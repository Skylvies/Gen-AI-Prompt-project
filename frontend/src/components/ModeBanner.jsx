export default function ModeBanner({ mode, config }) {
  if (mode === "demo") {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <strong>Demo Mode.</strong> Responses come from a built-in rule-based <em>simulator</em>, not a real language model. Token
        counts and latency are estimated. Scores show how the pipeline works; they say nothing about how a real model behaves.
      </div>
    );
  }
  const noPrice = config.price_input_per_mtok === 0 && config.price_output_per_mtok === 0;
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
      <strong>Real Mode</strong> &mdash; calls <code className="rounded bg-sky-100 px-1">{config.model}</code> via{" "}
      <strong>{config.provider}</strong>. Token usage and latency are measured. Each experiment makes one API call per selected
      technique using the server&apos;s API key (free tiers have rate limits, so very frequent runs may be slowed or refused).
      {noPrice && (
        <span className="mt-1 block text-sky-800">
          Cost shows as $0 because this model is free or has no price configured. To compare a paid-equivalent cost, set
          PRICE_INPUT_PER_MTOK and PRICE_OUTPUT_PER_MTOK on the server.
        </span>
      )}
    </div>
  );
}
