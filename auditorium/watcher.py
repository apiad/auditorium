import os, sys, time
import asyncio
import fire


class Watcher:
    def __init__(self, files, callback=None):
        self.files = files
        self.callback = callback

    def files_to_timestamp(self):
        return dict ([(f, os.path.getmtime(f)) for f in self.files])

    async def run(self):
        before = self.files_to_timestamp()

        while True:
            await asyncio.sleep(1)
            after = self.files_to_timestamp()

            modified = []

            for f in before.keys():
                if os.path.getmtime(f) != before.get(f):
                    modified.append(f)

            if modified: print('Modified: {}'.format(', '.join(modified)))

            before = after


if __name__ == "__main__":
    fire.Fire(Watcher)
