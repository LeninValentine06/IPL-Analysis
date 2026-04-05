"""
=============================================================================
  IPL PLAYER ERA ANALYSIS  2008-2026  |  Add-on to ipl_analysis.py
  Run independently OR after ipl_analysis.py (reuses the same JSON data)

  Generates 3 NEW charts + 1 detailed CSV:
    09_era_best_players.png        -- Top batter & bowler per era (scorecard style)
    10_cross_era_legends.png       -- Players dominant across 3+ eras
    11_performance_dip.png         -- Players whose form declined in a later era
    player_era_detailed.csv        -- Full per-player per-era breakdown

  pip install pandas numpy matplotlib seaborn scipy tqdm
=============================================================================
"""

import json, glob, os, sys, io, warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.ticker as mticker

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# =========================================================
#  CONFIG
# =========================================================
JSON_DIR   = r"C:\Users\lenin\Desktop\DS-Project\ipl_json"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipl_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Era definitions ──────────────────────────────────────
ERA_RANGES = {
    '2008-2012': (2008, 2012),
    '2013-2017': (2013, 2017),
    '2018-2022': (2018, 2022),
    '2023-2026': (2023, 2026),
}
ERAS       = list(ERA_RANGES.keys())
ERA_COLORS = ['#2471A3', '#17A589', '#E67E22', '#C0392B']
ERA_LIGHT  = ['#AED6F1', '#A2D9CE', '#FAD7A0', '#F1948A']

# ── Colour palette ────────────────────────────────────────
C = {
    'bg':      '#F4F6F9',
    'primary': '#0D1B2A',
    'gold':    '#E6A817',
    'red':     '#D62839',
    'blue':    '#1B4F72',
    'teal':    '#148F77',
    'orange':  '#CA6F1E',
    'purple':  '#6C3483',
    'green':   '#1E8449',
    'steel':   '#2E86C1',
    'grey':    '#717D7E',
}

plt.rcParams.update({
    'font.family':       'DejaVu Sans',
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.facecolor':    'white',
    'figure.facecolor':  C['bg'],
    'axes.labelcolor':   C['primary'],
    'xtick.color':       C['primary'],
    'ytick.color':       C['primary'],
    'text.color':        C['primary'],
    'axes.titleweight':  'bold',
    'axes.titlesize':    11,
})

# =========================================================
#  STEP 1 -- LOAD DATA
# =========================================================
def get_year(season):
    s = str(season)
    return int(s.split('/')[0]) if '/' in s else int(s[:4])

def assign_era(y):
    if y <= 2012: return '2008-2012'
    if y <= 2017: return '2013-2017'
    if y <= 2022: return '2018-2022'
    return '2023-2026'

def parse_match(fp):
    with open(fp, encoding='utf-8') as f:
        m = json.load(f)
    info     = m['info']
    year     = get_year(info.get('season', 0))
    match_id = os.path.basename(fp).replace('.json', '')
    rows     = []
    for inn_idx, inn in enumerate(m.get('innings', [])):
        for over_obj in inn.get('overs', []):
            ov    = over_obj['over']
            phase = ('Powerplay' if ov < 6 else
                     'Middle'    if ov < 15 else 'Death')
            for b in over_obj.get('deliveries', []):
                rb   = b['runs']['batter']
                rt   = b['runs']['total']
                ext  = b.get('extras', {})
                wide = 'wides'   in ext
                nb   = 'noballs' in ext
                legal= not wide and not nb
                wkts = b.get('wickets', [])
                rows.append({
                    'match_id':  match_id,
                    'year':      year,
                    'era':       assign_era(year),
                    'innings':   inn_idx + 1,
                    'phase':     phase,
                    'batter':    b['batter'],
                    'bowler':    b['bowler'],
                    'runs_bat':  rb,
                    'runs_tot':  rt,
                    'is_legal':  int(legal),
                    'is_four':   int(rb == 4),
                    'is_six':    int(rb == 6),
                    'is_dot':    int(rb == 0 and legal),
                    'is_bndry':  int(rb in (4, 6)),
                    'is_wicket': int(len(wkts) > 0),
                })
    return rows

def load_data():
    files = glob.glob(os.path.join(JSON_DIR, '*.json'))
    if not files:
        sys.exit(f"\nNo JSON files in: {JSON_DIR}")
    print(f"\n  {len(files)} files -- parsing...")
    rows = []
    it   = tqdm(files, unit='match') if HAS_TQDM else files
    for fp in it:
        try:
            rows.extend(parse_match(fp))
        except Exception as e:
            print(f"  SKIP {os.path.basename(fp)}: {e}")
    df = pd.DataFrame(rows)
    print(f"  {len(df):,} deliveries | {df['year'].min()}-{df['year'].max()}")
    return df

# =========================================================
#  STEP 2 -- BUILD PER-PLAYER PER-ERA STATS
# =========================================================
def build_player_era_stats(df):
    legal = df[df['is_legal'] == 1]

    # ── Batting ──────────────────────────────────────────
    bat = legal.groupby(['era', 'batter']).agg(
        runs    = ('runs_bat',  'sum'),
        balls   = ('is_legal',  'sum'),
        fours   = ('is_four',   'sum'),
        sixes   = ('is_six',    'sum'),
        dots    = ('is_dot',    'sum'),
        matches = ('match_id',  'nunique'),
        innings = ('innings',   'nunique'),
    ).reset_index()
    bat['sr']       = bat['runs'] / bat['balls'] * 100
    bat['avg']      = bat['runs'] / bat['innings']
    bat['bpct']     = (bat['fours'] + bat['sixes']) / bat['balls'] * 100
    bat['dot_pct']  = bat['dots'] / bat['balls'] * 100
    bat['six_pct']  = bat['sixes'] / (bat['fours'] + bat['sixes']).replace(0, np.nan) * 100
    # min 100 balls per era
    bat = bat[bat['balls'] >= 100].copy()

    # ── Bowling ──────────────────────────────────────────
    bowl = legal.groupby(['era', 'bowler']).agg(
        balls   = ('is_legal',  'sum'),
        runs    = ('runs_tot',  'sum'),
        wickets = ('is_wicket', 'sum'),
        dots    = ('is_dot',    'sum'),
        matches = ('match_id',  'nunique'),
    ).reset_index()
    bowl['economy'] = bowl['runs']  / bowl['balls'] * 6
    bowl['sr_bowl'] = bowl['balls'] / bowl['wickets'].replace(0, np.nan)
    bowl['avg_bow'] = bowl['runs']  / bowl['wickets'].replace(0, np.nan)
    bowl['dot_pct'] = bowl['dots']  / bowl['balls'] * 100
    # min 60 balls per era
    bowl = bowl[bowl['balls'] >= 60].copy()

    return bat, bowl

# =========================================================
#  STEP 3 -- COMPOSITE SCORES  (for ranking)
# =========================================================
def score_batters(bat_df):
    """
    Batting Impact Score = 0.4*(normalised runs) + 0.35*(normalised SR) + 0.25*(normalised avg)
    Higher is better.
    """
    df = bat_df.copy()
    for col in ['runs','sr','avg']:
        mn, mx = df[col].min(), df[col].max()
        df[f'_{col}_n'] = (df[col] - mn) / (mx - mn + 1e-9)
    df['bat_score'] = (0.40 * df['_runs_n'] +
                       0.35 * df['_sr_n']   +
                       0.25 * df['_avg_n'])
    return df

def score_bowlers(bowl_df):
    """
    Bowling Impact Score = 0.4*(normalised wickets) + 0.35*(inv-normalised economy) + 0.25*(inv-normalised sr_bowl)
    Higher is better.
    """
    df = bowl_df.copy()
    for col in ['wickets']:
        mn, mx = df[col].min(), df[col].max()
        df['_wkt_n'] = (df[col] - mn) / (mx - mn + 1e-9)
    for col in ['economy','sr_bowl']:
        mn, mx = df[col].min(), df[col].max()
        df[f'_{col}_n'] = 1 - (df[col] - mn) / (mx - mn + 1e-9)  # lower economy = better
    df['bowl_score'] = (0.40 * df['_wkt_n']     +
                        0.35 * df['_economy_n']  +
                        0.25 * df['_sr_bowl_n'])
    return df

# =========================================================
#  CHART 9 -- ERA-WISE BEST PLAYERS  (scorecard panels)
# =========================================================
def chart_era_best(bat, bowl):
    bat_s  = score_batters(bat)
    bowl_s = score_bowlers(bowl)

    fig = plt.figure(figsize=(22, 18), facecolor=C['bg'])
    fig.text(0.5, 0.985, 'ERA-WISE BEST PLAYERS  2008-2026',
             ha='center', va='top', fontsize=18, fontweight='bold', color=C['primary'])
    fig.text(0.5, 0.962, 'Top 6 batters & bowlers per era ranked by composite impact score  '
             '(runs + SR + avg  |  wickets + economy + strike rate)',
             ha='center', va='top', fontsize=9.5, color='#555', style='italic')

    # 4 eras x 2 columns (batters | bowlers)
    gs = gridspec.GridSpec(4, 2, figure=fig, hspace=0.55, wspace=0.30,
                           top=0.94, bottom=0.04, left=0.05, right=0.97)

    for row, (era, ec, el) in enumerate(zip(ERAS, ERA_COLORS, ERA_LIGHT)):

        # ── BATTERS panel ─────────────────────────────────
        ax_b = fig.add_subplot(gs[row, 0])
        top6 = (bat_s[bat_s['era'] == era]
                .nlargest(6, 'bat_score')
                .sort_values('bat_score'))

        y_pos = np.arange(len(top6))
        bars  = ax_b.barh(y_pos, top6['bat_score'], color=ec, alpha=0.85,
                           height=0.55, edgecolor='white')

        # stat labels on bars
        for i, (_, row_d) in enumerate(top6.iterrows()):
            ax_b.text(row_d['bat_score'] + 0.005,
                      y_pos[i],
                      f"Runs {row_d['runs']:.0f}  SR {row_d['sr']:.0f}  "
                      f"Avg {row_d['avg']:.1f}  B% {row_d['bpct']:.0f}",
                      va='center', fontsize=7, color=C['primary'])

        ax_b.set_yticks(y_pos)
        ax_b.set_yticklabels(top6['batter'], fontsize=8.5)
        ax_b.set_xlim(0, top6['bat_score'].max() * 1.55)
        ax_b.set_xlabel('Composite Impact Score', fontsize=8)
        ax_b.set_title(f'[{era}]  TOP BATTERS', color=ec, fontsize=11, pad=6)
        ax_b.tick_params(axis='x', labelsize=7)

        # era badge
        ax_b.text(0.98, 0.98, era, transform=ax_b.transAxes,
                  ha='right', va='top', fontsize=8, color='white',
                  fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.3', fc=ec, ec='none', alpha=0.85))

        # ── BOWLERS panel ─────────────────────────────────
        ax_w = fig.add_subplot(gs[row, 1])
        top6w = (bowl_s[bowl_s['era'] == era]
                 .nlargest(6, 'bowl_score')
                 .sort_values('bowl_score'))

        y_posw = np.arange(len(top6w))
        ax_w.barh(y_posw, top6w['bowl_score'], color=ec, alpha=0.72,
                  height=0.55, edgecolor='white')

        for i, (_, row_d) in enumerate(top6w.iterrows()):
            ax_w.text(row_d['bowl_score'] + 0.005,
                      y_posw[i],
                      f"Wkts {row_d['wickets']:.0f}  Eco {row_d['economy']:.2f}  "
                      f"SR {row_d['sr_bowl']:.1f}  Dot {row_d['dot_pct']:.0f}%",
                      va='center', fontsize=7, color=C['primary'])

        ax_w.set_yticks(y_posw)
        ax_w.set_yticklabels(top6w['bowler'], fontsize=8.5)
        ax_w.set_xlim(0, top6w['bowl_score'].max() * 1.55)
        ax_w.set_xlabel('Composite Impact Score', fontsize=8)
        ax_w.set_title(f'[{era}]  TOP BOWLERS', color=ec, fontsize=11, pad=6)
        ax_w.tick_params(axis='x', labelsize=7)
        ax_w.text(0.98, 0.98, era, transform=ax_w.transAxes,
                  ha='right', va='top', fontsize=8, color='white',
                  fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.3', fc=ec, ec='none', alpha=0.85))

    p = os.path.join(OUTPUT_DIR, '09_era_best_players.png')
    fig.savefig(p, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close(fig)
    print('  Saved  09_era_best_players.png')

# =========================================================
#  CHART 10 -- CROSS-ERA LEGENDS
#  Players who were among the top performers in 3 or 4 eras
# =========================================================
def chart_cross_era_legends(bat, bowl):
    bat_s  = score_batters(bat)
    bowl_s = score_bowlers(bowl)

    # For each era get top-N per metric
    TOP_N_BAT  = 10
    TOP_N_BOWL = 10

    # Count how many eras each player appears in top-N
    bat_era_top = (bat_s.groupby('era')
                        .apply(lambda g: g.nlargest(TOP_N_BAT, 'bat_score')['batter'])
                        .reset_index(level=0)
                        .reset_index(drop=True))
    bat_era_top.columns = ['era','batter']

    bowl_era_top = (bowl_s.groupby('era')
                          .apply(lambda g: g.nlargest(TOP_N_BOWL, 'bowl_score')['bowler'])
                          .reset_index(level=0)
                          .reset_index(drop=True))
    bowl_era_top.columns = ['era','bowler']

    bat_counts  = bat_era_top.groupby('batter')['era'].nunique().reset_index(name='eras_count')
    bowl_counts = bowl_era_top.groupby('bowler')['era'].nunique().reset_index(name='eras_count')

    # Players in 3+ eras
    legends_bat  = bat_counts[bat_counts['eras_count'] >= 3].sort_values('eras_count', ascending=False)
    legends_bowl = bowl_counts[bowl_counts['eras_count'] >= 3].sort_values('eras_count', ascending=False)

    # Fall back to 2+ eras if fewer than 3 legends found
    if len(legends_bat) < 3:
        legends_bat  = bat_counts[bat_counts['eras_count'] >= 2].sort_values('eras_count', ascending=False)
    if len(legends_bowl) < 3:
        legends_bowl = bowl_counts[bowl_counts['eras_count'] >= 2].sort_values('eras_count', ascending=False)

    # Pull full per-era stats for legends
    bat_legend_detail  = bat_s[bat_s['batter'].isin(legends_bat['batter'].head(8))]
    bowl_legend_detail = bowl_s[bowl_s['bowler'].isin(legends_bowl['bowler'].head(8))]

    fig = plt.figure(figsize=(22, 16), facecolor=C['bg'])
    fig.text(0.5, 0.985, 'CROSS-ERA LEGENDS  --  Players Dominant Across Multiple Eras',
             ha='center', va='top', fontsize=17, fontweight='bold', color=C['primary'])
    fig.text(0.5, 0.962,
             'Batters & bowlers who ranked in the top 10 across 3 or more IPL eras',
             ha='center', va='top', fontsize=9.5, color='#555', style='italic')

    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.52, wspace=0.35,
                           top=0.93, bottom=0.05, left=0.06, right=0.97)

    # ── Panel A: Legend batter -- runs per era (grouped bar) ──
    ax1 = fig.add_subplot(gs[0, 0])
    legend_bat_top = legends_bat['batter'].head(8).tolist()
    pivot_runs = (bat_legend_detail[bat_legend_detail['batter'].isin(legend_bat_top)]
                  .pivot_table(index='batter', columns='era', values='runs', fill_value=0)
                  .reindex(columns=ERAS, fill_value=0))

    x      = np.arange(len(pivot_runs))
    bar_w  = 0.18
    for i, (era, col) in enumerate(zip(ERAS, ERA_COLORS)):
        vals = pivot_runs[era].values if era in pivot_runs.columns else np.zeros(len(pivot_runs))
        ax1.bar(x + i*bar_w, vals, bar_w, label=era, color=col, alpha=0.85, edgecolor='white')

    ax1.set_xticks(x + bar_w*1.5)
    ax1.set_xticklabels(pivot_runs.index, rotation=25, ha='right', fontsize=8)
    ax1.set(title='Legend Batters -- Runs per Era', ylabel='Runs')
    ax1.legend(frameon=False, fontsize=7.5, ncol=2)

    # ── Panel B: Legend batter -- SR per era (line plot) ──────
    ax2 = fig.add_subplot(gs[0, 1])
    bat_leg_top5 = legends_bat['batter'].head(5).tolist()
    player_colors = plt.cm.tab10(np.linspace(0, 0.9, len(bat_leg_top5)))
    for player, col in zip(bat_leg_top5, player_colors):
        sub = (bat_legend_detail[bat_legend_detail['batter'] == player]
               .sort_values('era'))
        if len(sub) >= 2:
            ax2.plot(sub['era'], sub['sr'], 'o-', label=player,
                     color=col, lw=2, ms=6)
            # annotate last point
            last = sub.iloc[-1]
            ax2.annotate(player, (last['era'], last['sr']),
                         xytext=(4, 0), textcoords='offset points',
                         fontsize=7, color=col)
    ax2.set(title='Legend Batters -- Strike Rate Across Eras',
            xlabel='Era', ylabel='Strike Rate')
    ax2.tick_params(axis='x', labelsize=8)

    # ── Panel C: Legend bowler -- wickets per era ─────────────
    ax3 = fig.add_subplot(gs[1, 0])
    legend_bowl_top = legends_bowl['bowler'].head(8).tolist()
    pivot_wkts = (bowl_legend_detail[bowl_legend_detail['bowler'].isin(legend_bowl_top)]
                  .pivot_table(index='bowler', columns='era', values='wickets', fill_value=0)
                  .reindex(columns=ERAS, fill_value=0))

    x2 = np.arange(len(pivot_wkts))
    for i, (era, col) in enumerate(zip(ERAS, ERA_COLORS)):
        vals2 = pivot_wkts[era].values if era in pivot_wkts.columns else np.zeros(len(pivot_wkts))
        ax3.bar(x2 + i*bar_w, vals2, bar_w, label=era, color=col, alpha=0.85, edgecolor='white')

    ax3.set_xticks(x2 + bar_w*1.5)
    ax3.set_xticklabels(pivot_wkts.index, rotation=25, ha='right', fontsize=8)
    ax3.set(title='Legend Bowlers -- Wickets per Era', ylabel='Wickets')
    ax3.legend(frameon=False, fontsize=7.5, ncol=2)

    # ── Panel D: Legend bowler -- economy per era ─────────────
    ax4 = fig.add_subplot(gs[1, 1])
    bowl_leg_top5 = legends_bowl['bowler'].head(5).tolist()
    bow_colors = plt.cm.tab10(np.linspace(0, 0.9, len(bowl_leg_top5)))
    for player, col in zip(bowl_leg_top5, bow_colors):
        sub = (bowl_legend_detail[bowl_legend_detail['bowler'] == player]
               .sort_values('era'))
        if len(sub) >= 2:
            ax4.plot(sub['era'], sub['economy'], 'D-', label=player,
                     color=col, lw=2, ms=6)
            last = sub.iloc[-1]
            ax4.annotate(player, (last['era'], last['economy']),
                         xytext=(4, 0), textcoords='offset points',
                         fontsize=7, color=col)
    ax4.set(title='Legend Bowlers -- Economy Rate Across Eras',
            xlabel='Era', ylabel='Economy (RPO)')
    ax4.tick_params(axis='x', labelsize=8)

    p = os.path.join(OUTPUT_DIR, '10_cross_era_legends.png')
    fig.savefig(p, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close(fig)
    print('  Saved  10_cross_era_legends.png')

    return legends_bat, legends_bowl

# =========================================================
#  CHART 11 -- PERFORMANCE DIP ANALYSIS
#  Players who were top performers in an earlier era but
#  clearly declined in a subsequent era
# =========================================================
def chart_performance_dip(bat, bowl):
    bat_s  = score_batters(bat)
    bowl_s = score_bowlers(bowl)

    # For batters: find players present in consecutive eras with score drop
    def find_dippers_bat(df, score_col='bat_score', name_col='batter', min_balls=150):
        df = df[df['balls'] >= min_balls].copy()
        results = []
        era_list = ERAS
        for i in range(len(era_list) - 1):
            era_now  = era_list[i]
            era_next = era_list[i + 1]
            now  = df[df['era'] == era_now][[name_col, score_col, 'runs', 'sr', 'avg', 'balls']]
            nxt  = df[df['era'] == era_next][[name_col, score_col, 'runs', 'sr', 'avg', 'balls']]
            merged = now.merge(nxt, on=name_col, suffixes=('_old','_new'))
            merged['score_drop'] = merged[f'{score_col}_old'] - merged[f'{score_col}_new']
            merged['era_old']    = era_now
            merged['era_new']    = era_next
            # Only genuine droppers: score was decent before, dropped meaningfully
            dippers = merged[
                (merged[f'{score_col}_old'] > merged[f'{score_col}_old'].quantile(0.6)) &
                (merged['score_drop'] > 0.12)
            ].nlargest(4, 'score_drop')
            results.append(dippers)
        return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

    def find_dippers_bowl(df, score_col='bowl_score', name_col='bowler', min_balls=60):
        df = df[df['balls'] >= min_balls].copy()
        results = []
        era_list = ERAS
        for i in range(len(era_list) - 1):
            era_now  = era_list[i]
            era_next = era_list[i + 1]
            now  = df[df['era'] == era_now][[name_col, score_col, 'wickets', 'economy', 'balls']]
            nxt  = df[df['era'] == era_next][[name_col, score_col, 'wickets', 'economy', 'balls']]
            merged = now.merge(nxt, on=name_col, suffixes=('_old','_new'))
            merged['score_drop'] = merged[f'{score_col}_old'] - merged[f'{score_col}_new']
            merged['era_old']    = era_now
            merged['era_new']    = era_next
            dippers = merged[
                (merged[f'{score_col}_old'] > merged[f'{score_col}_old'].quantile(0.6)) &
                (merged['score_drop'] > 0.10)
            ].nlargest(4, 'score_drop')
            results.append(dippers)
        return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

    bat_dip  = find_dippers_bat(bat_s)
    bowl_dip = find_dippers_bowl(bowl_s)

    # ── Build per-player full trajectory for dippers ──────────
    def full_trajectory(df, players, name_col, score_col, stat1, stat2):
        """Get all era stats for a list of players."""
        return df[df[name_col].isin(players)].copy()

    top_bat_dippers  = bat_dip[bat_dip['batter'].notna()]['batter'].unique()[:8] if len(bat_dip) > 0 else []
    top_bowl_dippers = bowl_dip[bowl_dip['bowler'].notna()]['bowler'].unique()[:8] if len(bowl_dip) > 0 else []

    bat_traj  = full_trajectory(bat_s,  top_bat_dippers,  'batter', 'bat_score',  'runs', 'sr')
    bowl_traj = full_trajectory(bowl_s, top_bowl_dippers, 'bowler', 'bowl_score', 'wickets', 'economy')

    fig = plt.figure(figsize=(22, 18), facecolor=C['bg'])
    fig.text(0.5, 0.985,
             'PERFORMANCE DIP ANALYSIS  --  Rise & Fall Across Eras',
             ha='center', va='top', fontsize=17, fontweight='bold', color=C['primary'])
    fig.text(0.5, 0.962,
             'Players who were dominant in earlier eras but saw significant decline in later ones',
             ha='center', va='top', fontsize=9.5, color='#555', style='italic')

    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.55, wspace=0.35,
                           top=0.93, bottom=0.04, left=0.06, right=0.97)

    # ── Panel A: Batter score trajectory (line) ───────────────
    ax1 = fig.add_subplot(gs[0, :])
    player_colors = plt.cm.tab10(np.linspace(0, 0.9, max(len(top_bat_dippers), 1)))
    for player, col in zip(top_bat_dippers, player_colors):
        sub = bat_traj[bat_traj['batter'] == player].sort_values('era')
        if len(sub) >= 2:
            ax1.plot(sub['era'], sub['bat_score'], 'o-',
                     label=player, color=col, lw=2.5, ms=7, zorder=3)
            # shade the drop
            for j in range(len(sub) - 1):
                if sub.iloc[j+1]['bat_score'] < sub.iloc[j]['bat_score']:
                    ax1.annotate('', xy=(sub.iloc[j+1]['era'], sub.iloc[j+1]['bat_score']),
                                 xytext=(sub.iloc[j]['era'], sub.iloc[j]['bat_score']),
                                 arrowprops=dict(arrowstyle='->', color=col,
                                                 lw=1.5, linestyle='dashed'))
            # label player at peak
            peak = sub.loc[sub['bat_score'].idxmax()]
            ax1.annotate(f"  {player}", (peak['era'], peak['bat_score']),
                         fontsize=7.5, color=col, va='bottom')
    # era background bands
    for s, era, ec, el in zip(range(4), ERAS, ERA_COLORS, ERA_LIGHT):
        ax1.axvspan(s-0.4, s+0.4, color=ec, alpha=0.07, zorder=0)
    ax1.set(title='Batter Impact Score Trajectory  (arrows show decline)',
            xlabel='Era', ylabel='Composite Impact Score')
    ax1.tick_params(axis='x', labelsize=8.5)
    ax1.legend(frameon=False, fontsize=8, ncol=4, loc='upper right')

    # ── Panel B: Batter -- runs before vs after drop ──────────
    ax2 = fig.add_subplot(gs[1, 0])
    if len(bat_dip) > 0:
        bat_dip_top = bat_dip.drop_duplicates('batter').head(8).copy()
        bat_dip_top = bat_dip_top.sort_values('score_drop', ascending=True)
        y_b = np.arange(len(bat_dip_top))
        # before runs
        ax2.barh(y_b - 0.2, bat_dip_top['runs_old'], 0.38,
                 color=C['steel'], alpha=0.85, label='Before (peak era)')
        ax2.barh(y_b + 0.2, bat_dip_top['runs_new'], 0.38,
                 color=C['red'],   alpha=0.75, label='After (decline era)')
        ax2.set_yticks(y_b)
        ax2.set_yticklabels(bat_dip_top['batter'], fontsize=8.5)
        ax2.set(title='Batter Runs: Peak Era vs Decline Era', xlabel='Runs')
        ax2.legend(frameon=False, fontsize=8)
        # annotate SR change
        for i, (_, r) in enumerate(bat_dip_top.iterrows()):
            ax2.text(max(r['runs_old'], r['runs_new']) + 10, y_b[i],
                     f"SR: {r['sr_old']:.0f} -> {r['sr_new']:.0f}",
                     va='center', fontsize=7, color=C['grey'])

    # ── Panel C: Batter -- SR before vs after ─────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    if len(bat_dip) > 0:
        bat_dip_top2 = bat_dip.drop_duplicates('batter').head(8).copy()
        bat_dip_top2 = bat_dip_top2.sort_values('score_drop', ascending=True)
        y_c = np.arange(len(bat_dip_top2))
        ax3.barh(y_c - 0.2, bat_dip_top2['sr_old'], 0.38,
                 color=C['steel'], alpha=0.85, label='SR Before')
        ax3.barh(y_c + 0.2, bat_dip_top2['sr_new'], 0.38,
                 color=C['red'],   alpha=0.75, label='SR After')
        ax3.set_yticks(y_c)
        ax3.set_yticklabels(bat_dip_top2['batter'], fontsize=8.5)
        ax3.set(title='Batter Strike Rate: Peak Era vs Decline Era', xlabel='Strike Rate')
        ax3.legend(frameon=False, fontsize=8)
        ax3.axvline(100, color=C['grey'], lw=0.8, ls='--', alpha=0.5)

    # ── Panel D: Bowler score trajectory ──────────────────────
    ax4 = fig.add_subplot(gs[2, 0])
    bow_colors = plt.cm.tab10(np.linspace(0, 0.9, max(len(top_bowl_dippers), 1)))
    for player, col in zip(top_bowl_dippers, bow_colors):
        sub = bowl_traj[bowl_traj['bowler'] == player].sort_values('era')
        if len(sub) >= 2:
            ax4.plot(sub['era'], sub['bowl_score'], 's-',
                     label=player, color=col, lw=2, ms=6)
            last = sub.iloc[-1]
            ax4.annotate(f"  {player}", (last['era'], last['bowl_score']),
                         fontsize=7.5, color=col)
    ax4.set(title='Bowler Impact Score Trajectory', xlabel='Era', ylabel='Composite Impact Score')
    ax4.legend(frameon=False, fontsize=7.5, ncol=2)
    ax4.tick_params(axis='x', labelsize=8)

    # ── Panel E: Bowler economy before vs after ────────────────
    ax5 = fig.add_subplot(gs[2, 1])
    if len(bowl_dip) > 0:
        bowl_dip_top = bowl_dip.drop_duplicates('bowler').head(8).copy()
        bowl_dip_top = bowl_dip_top.sort_values('score_drop', ascending=True)
        y_e = np.arange(len(bowl_dip_top))
        ax5.barh(y_e - 0.2, bowl_dip_top['wickets_old'], 0.38,
                 color=C['teal'], alpha=0.85, label='Wickets Before')
        ax5.barh(y_e + 0.2, bowl_dip_top['wickets_new'], 0.38,
                 color=C['red'],  alpha=0.75, label='Wickets After')
        ax5.set_yticks(y_e)
        ax5.set_yticklabels(bowl_dip_top['bowler'], fontsize=8.5)
        ax5.set(title='Bowler Wickets: Peak Era vs Decline Era', xlabel='Wickets')
        ax5.legend(frameon=False, fontsize=8)
        for i, (_, r) in enumerate(bowl_dip_top.iterrows()):
            ax5.text(max(r['wickets_old'], r['wickets_new']) + 0.5, y_e[i],
                     f"Eco: {r['economy_old']:.1f} -> {r['economy_new']:.1f}",
                     va='center', fontsize=7, color=C['grey'])

    p = os.path.join(OUTPUT_DIR, '11_performance_dip.png')
    fig.savefig(p, dpi=150, bbox_inches='tight', facecolor=C['bg'])
    plt.close(fig)
    print('  Saved  11_performance_dip.png')

    return bat_dip, bowl_dip

# =========================================================
#  EXPORT DETAILED CSV
# =========================================================
def export_player_era_csv(bat, bowl):
    bat_s  = score_batters(bat)
    bowl_s = score_bowlers(bowl)

    # Batting CSV
    bat_out = bat_s[[
        'era','batter','runs','balls','innings','matches',
        'sr','avg','bpct','dot_pct','six_pct','bat_score'
    ]].copy()
    bat_out.columns = [
        'era','player','runs','balls_faced','innings','matches',
        'strike_rate','avg_per_innings','boundary_pct','dot_pct',
        'six_of_boundaries_pct','impact_score'
    ]
    bat_out = bat_out.sort_values(['era','impact_score'], ascending=[True,False])

    # Bowling CSV
    bowl_out = bowl_s[[
        'era','bowler','wickets','balls','matches',
        'economy','sr_bowl','avg_bow','dot_pct','bowl_score'
    ]].copy()
    bowl_out.columns = [
        'era','player','wickets','balls_bowled','matches',
        'economy','bowling_sr','bowling_avg','dot_pct','impact_score'
    ]
    bowl_out = bowl_out.sort_values(['era','impact_score'], ascending=[True,False])

    bat_out.to_csv(os.path.join(OUTPUT_DIR, 'player_era_batting_detailed.csv'),  index=False)
    bowl_out.to_csv(os.path.join(OUTPUT_DIR, 'player_era_bowling_detailed.csv'), index=False)
    print('  Saved  player_era_batting_detailed.csv')
    print('  Saved  player_era_bowling_detailed.csv')

# =========================================================
#  PRINT SUMMARY TABLE
# =========================================================
def print_summary(bat, bowl, legends_bat, legends_bowl, bat_dip, bowl_dip):
    bat_s  = score_batters(bat)
    bowl_s = score_bowlers(bowl)

    report = """
=============================================================================
  IPL PLAYER ERA ANALYSIS -- SUMMARY REPORT
=============================================================================

--- ERA-WISE BEST BATTERS (Composite: 40% runs + 35% SR + 25% avg) ---
"""
    for era, ec in zip(ERAS, ERA_COLORS):
        top3 = bat_s[bat_s['era']==era].nlargest(3,'bat_score')
        report += f"\n  {era}:\n"
        for _, r in top3.iterrows():
            report += (f"    {r['batter']:<22}  Runs {r['runs']:>4.0f}  "
                       f"SR {r['sr']:>5.1f}  Avg {r['avg']:>5.1f}  "
                       f"B% {r['bpct']:>4.0f}  Score {r['bat_score']:.3f}\n")

    report += "\n--- ERA-WISE BEST BOWLERS (Composite: 40% wkts + 35% eco + 25% SR) ---\n"
    for era in ERAS:
        top3 = bowl_s[bowl_s['era']==era].nlargest(3,'bowl_score')
        report += f"\n  {era}:\n"
        for _, r in top3.iterrows():
            report += (f"    {r['bowler']:<22}  Wkts {r['wickets']:>3.0f}  "
                       f"Eco {r['economy']:>4.2f}  SR {r['sr_bowl']:>5.1f}  "
                       f"Dot {r['dot_pct']:>4.0f}%  Score {r['bowl_score']:.3f}\n")

    report += "\n--- CROSS-ERA LEGENDS (Top 10 in 3+ eras) ---\n"
    if len(legends_bat) > 0:
        report += "\n  Batters:\n"
        for _, r in legends_bat.head(8).iterrows():
            report += f"    {r['batter']:<22}  Active in {r['eras_count']} eras\n"
    if len(legends_bowl) > 0:
        report += "\n  Bowlers:\n"
        for _, r in legends_bowl.head(8).iterrows():
            report += f"    {r['bowler']:<22}  Active in {r['eras_count']} eras\n"

    report += "\n--- PERFORMANCE DIP -- BATTERS ---\n"
    if len(bat_dip) > 0:
        shown = set()
        for _, r in bat_dip.iterrows():
            if r['batter'] not in shown:
                report += (f"  {r['batter']:<22}  {r['era_old']} -> {r['era_new']}  "
                           f"Runs {r['runs_old']:.0f}->{r['runs_new']:.0f}  "
                           f"SR {r['sr_old']:.0f}->{r['sr_new']:.0f}  "
                           f"Drop {r['score_drop']:.3f}\n")
                shown.add(r['batter'])

    report += "\n--- PERFORMANCE DIP -- BOWLERS ---\n"
    if len(bowl_dip) > 0:
        shown = set()
        for _, r in bowl_dip.iterrows():
            if r['bowler'] not in shown:
                report += (f"  {r['bowler']:<22}  {r['era_old']} -> {r['era_new']}  "
                           f"Wkts {r['wickets_old']:.0f}->{r['wickets_new']:.0f}  "
                           f"Eco {r['economy_old']:.2f}->{r['economy_new']:.2f}  "
                           f"Drop {r['score_drop']:.3f}\n")
                shown.add(r['bowler'])

    report += f"""
=============================================================================
  Output files -> {OUTPUT_DIR}
    09_era_best_players.png          Era-wise top batters & bowlers
    10_cross_era_legends.png         Multi-era dominant players
    11_performance_dip.png           Players who declined across eras
    player_era_batting_detailed.csv  Full batting breakdown by era
    player_era_bowling_detailed.csv  Full bowling breakdown by era
=============================================================================
"""
    path = os.path.join(OUTPUT_DIR, 'player_era_report.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)

# =========================================================
#  MAIN
# =========================================================
def main():
    print('=' * 62)
    print('  IPL PLAYER ERA ANALYSIS  2008-2026')
    print('=' * 62)

    df = load_data()

    print('\n  Building player-era stats...')
    bat, bowl = build_player_era_stats(df)
    print(f'  {len(bat)} batter-era records | {len(bowl)} bowler-era records')

    print('\n  Generating charts...')
    chart_era_best(bat, bowl)
    legends_bat, legends_bowl = chart_cross_era_legends(bat, bowl)
    bat_dip, bowl_dip         = chart_performance_dip(bat, bowl)

    print('\n  Exporting CSVs...')
    export_player_era_csv(bat, bowl)

    print('\n  Writing summary report...')
    print_summary(bat, bowl, legends_bat, legends_bowl, bat_dip, bowl_dip)

    print(f'\n  Done!  All files in: {OUTPUT_DIR}\n')

if __name__ == '__main__':
    main()
