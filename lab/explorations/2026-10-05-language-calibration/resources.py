"""Final bounded storage receipt; no content hashes or archived-state rereads."""
import json
import shutil
import time

import psutil
from experiment import HERE, WORK, read_json

from lab.tools.service_study import new_json
from lab.tools.study_publication import ArchivedStudy, Publication


def main():
    study=ArchivedStudy(WORK)
    try:
        files=[p for p in WORK.rglob('*') if p.is_file()]
        total=sum(p.stat().st_size for p in files)
        archive=WORK/'evidence.zip'
        archive_bytes=archive.stat().st_size if archive.exists() else 0
        with study.db.tx() as tx:
            database=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        growth=max(0,database-study.meta['database_bytes_before'])
        result={'recorded_at_epoch':time.time(),'local_total_bytes':total,'archive_bytes':archive_bytes,
            'local_without_archive_bytes':total-archive_bytes,'database_growth_bytes':growth,
            'combined_bytes':total+growth,'hard_limit_bytes':study.settings.storage_hard,
            'database_growth_scope':'whole database growth; other work conservatively included',
            'account_start_percent':study.settings.usage_start,'account_latest_percent':read_json(WORK/'usage.json')['used_percent'],
            'account_scope':'shared account, not this experiment alone',
            'available_ram_bytes':psutil.virtual_memory().available,
            'free_c_bytes':shutil.disk_usage('C:/').free,'free_e_bytes':shutil.disk_usage('E:/').free,
            'measurement':'post-publication snapshot; not an observed peak',
            'recorded_compute_seconds':read_json(HERE/'results.json')['recorded_compute_seconds']}
        if total+growth>study.settings.storage_hard:raise RuntimeError('combined evidence budget exceeded')
        new_json(HERE/'resource-use.json',result)
        Publication(study).note('resource-final','E45 Final resource receipt',
            '本值是主要证据发布后的资源快照，不是持续峰值；账户和数据库增长包括其他任务。 / '
            'Snapshot after main evidence publication, not observed peaks; shared account/database growth includes other work.\n\n'
            + json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result))
    finally:study.db.close()


if __name__=='__main__':main()
