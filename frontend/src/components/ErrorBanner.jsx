import './ErrorBanner.css';

// Short labels for the failure kinds the backend reports. The hint that comes
// with each error already names the fix, so these only set the tone.
const KIND_LABELS = {
  auth: 'Authentication failed',
  credit: 'Out of credit',
  forbidden: 'Not permitted',
  model_not_found: 'Unknown model',
  rate_limit: 'Rate limited',
  timeout: 'Timed out',
  network: 'Provider unreachable',
  provider_error: 'Provider error',
  empty_response: 'Empty response',
  bad_request: 'Bad request',
  storage: 'Conversation not saved',
  all_failed: 'Council failed',
  http_error: 'Request failed',
  unknown: 'Failed',
};

const STAGE_LABELS = {
  stage1: 'answering',
  stage2: 'reviewing',
  stage3: 'chairing',
  storage: 'saving',
};

/**
 * Reports the failures a round hit. A model that errors is dropped from the
 * council rather than failing the request, so without this the only symptom is a
 * tab that quietly is not there.
 */
export default function ErrorBanner({ errors, councilSize, fatal }) {
  if (!errors || errors.length === 0) {
    return null;
  }

  const failedMembers = errors.filter((e) => e.stage === 'stage1').length;
  const severity = fatal || failedMembers === councilSize ? 'fatal' : 'warning';

  return (
    <div className={`error-banner ${severity}`}>
      <div className="error-banner-title">
        {severity === 'fatal'
          ? 'This round failed'
          : `${errors.length} ${errors.length === 1 ? 'problem' : 'problems'} this round`}
        {councilSize && failedMembers > 0 && (
          <span className="error-banner-count">
            {' '}
            &middot; {failedMembers} of {councilSize} council{' '}
            {failedMembers === 1 ? 'member' : 'members'} dropped out
          </span>
        )}
      </div>

      <ul className="error-list">
        {errors.map((error, index) => (
          <li key={`${error.model}-${error.stage}-${index}`}>
            <div className="error-head">
              <code className="error-model">{error.model}</code>
              <span className="error-kind">
                {KIND_LABELS[error.kind] || 'Failed'}
                {error.status ? ` (${error.status})` : ''}
              </span>
              {STAGE_LABELS[error.stage] && (
                <span className="error-stage">while {STAGE_LABELS[error.stage]}</span>
              )}
            </div>
            {error.hint && <div className="error-hint">{error.hint}</div>}
            {error.message && <div className="error-detail">{error.message}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
