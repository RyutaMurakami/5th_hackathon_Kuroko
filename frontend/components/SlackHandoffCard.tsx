import type { Handoff } from "@/lib/types";
import { Icon } from "./Icon";
import { ButtonLink, Caption, Pill, TextLink } from "./ui";
import styles from "./event.module.css";

// 本番では、ワークスペースの Slack のディープリンクを API から受け取る
const SLACK_URL = "https://slack.com/";

/**
 * Slack で人の対応が要る場面（Human-in-the-loop）。DESIGN.md「Slack Handoff Card」。
 * Web には、承認・委任・取り消し・振込を実行するボタンを置かない。
 */
export function SlackHandoffCard({ handoff }: { handoff: Handoff }) {
  return (
    <section className={styles.handoff} aria-label="Slack で対応待ち">
      <div className={styles.handoffBody}>
        <Pill tone="sun">Slack で対応待ち</Pill>
        <p className={styles.handoffText}>
          <strong>{handoff.who}</strong>
          {handoff.what}
        </p>
        <Caption>{handoff.detail}</Caption>
        {handoff.demoProxy && (
          <div className={styles.proxyBand}>
            <span>{handoff.demoProxy}</span>
            <TextLink href={SLACK_URL} external>
              Slack に参加して承認する
            </TextLink>
          </div>
        )}
      </div>
      <ButtonLink variant="secondary" href={SLACK_URL} external>
        <Icon name="slack" />
        Slack で開く
      </ButtonLink>
    </section>
  );
}
