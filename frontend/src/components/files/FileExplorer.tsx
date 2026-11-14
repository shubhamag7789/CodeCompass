import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Search,
  FileCode,
  Copy,
  Check,
  FolderTree,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { api } from '../../api/client';

interface FileExplorerProps {
  files: string[];
  activeRepoId?: string;
  selectedFile?: string;
  onSelectFile?: (filePath: string) => void;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  activeRepoId,
  selectedFile: initialFile,
  onSelectFile,
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const initialValid = initialFile && files.includes(initialFile) ? initialFile : (files[0] || '');
  const [currentFile, setCurrentFile] = useState<string>(initialValid);
  const [fileContent, setFileContent] = useState<string>('');
  const [lineCount, setLineCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const selectedItemRef = useRef<HTMLDivElement>(null);

  // Sync when initialFile or files changes
  useEffect(() => {
    if (initialFile && files.includes(initialFile)) {
      if (initialFile !== currentFile) {
        setCurrentFile(initialFile);
      }
    } else if (files.length > 0 && (!currentFile || !files.includes(currentFile))) {
      setCurrentFile(files[0]);
    }
  }, [initialFile, files]);

  // Filter files
  const filteredFiles = useMemo(() => {
    if (!filterQuery.trim()) return files;
    const q = filterQuery.toLowerCase();
    return files.filter((f) => f.toLowerCase().includes(q));
  }, [files, filterQuery]);

  // Scroll active item into view
  useEffect(() => {
    if (selectedItemRef.current) {
      selectedItemRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [currentFile]);

  // Load content when current file changes
  useEffect(() => {
    if (!currentFile) return;
    let isCurrent = true;
    setIsLoading(true);

    api
      .getFileContent(currentFile, activeRepoId)
      .then((res) => {
        if (!isCurrent) return;
        setFileContent(res.content || '');
        setLineCount(res.lines || (res.content ? res.content.split('\n').length : 0));
      })
      .catch(() => {
        if (!isCurrent) return;
        setFileContent('// Unable to load file content or file is binary/inaccessible.');
        setLineCount(0);
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [currentFile, activeRepoId]);

  const handleSelect = (file: string) => {
    setCurrentFile(file);
    if (onSelectFile) onSelectFile(file);
  };

  const handleCopy = () => {
    if (!fileContent) return;
    navigator.clipboard.writeText(fileContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getExtensionBadge = (path: string) => {
    const ext = path.split('.').pop()?.toUpperCase() || 'FILE';
    let color = 'bg-slate-800 text-slate-400 border-slate-700';
    if (['JS', 'JSX'].includes(ext)) color = 'bg-amber-500/10 text-amber-300 border-amber-500/20';
    else if (['TS', 'TSX'].includes(ext)) color = 'bg-blue-500/10 text-blue-300 border-blue-500/20';
    else if (['PY'].includes(ext)) color = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20';
    else if (['JSON', 'YAML', 'YML'].includes(ext)) color = 'bg-purple-500/10 text-purple-300 border-purple-500/20';
    else if (['CSS', 'SCSS', 'HTML'].includes(ext)) color = 'bg-pink-500/10 text-pink-300 border-pink-500/20';

    return (
      <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-bold border ${color}`}>
        {ext}
      </span>
    );
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-[#0c101d]">
      {/* Sidebar: File List */}
      <div className="w-80 flex-shrink-0 border-r border-white/5 flex flex-col bg-[#0c101d]/60 backdrop-blur-md">
        {/* Search header */}
        <div className="p-3 border-b border-white/5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
              <FolderTree className="w-3.5 h-3.5 text-cyan-400" />
              <span>Repository Files</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              {filteredFiles.length} / {files.length}
            </span>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-slate-500" />
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter files by name or folder..."
              className="w-full bg-slate-900/80 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>
        </div>

        {/* Scrollable File Cards List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {filteredFiles.map((file) => {
            const isSelected = file === currentFile;
            const parts = file.split('/');
            const fileName = parts.pop() || file;
            const dirPath = parts.join('/');

            return (
              <div
                key={file}
                ref={isSelected ? selectedItemRef : undefined}
                onClick={() => handleSelect(file)}
                className={`p-2 rounded-xl cursor-pointer transition-all border text-left ${
                  isSelected
                    ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-100 shadow-lg shadow-cyan-500/5 ring-1 ring-cyan-500/30'
                    : 'glass-card border-white/5 hover:border-white/10 text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold truncate text-white mr-2">
                    {fileName}
                  </span>
                  {getExtensionBadge(fileName)}
                </div>
                {dirPath && (
                  <div className="text-[10px] text-slate-400 truncate mt-0.5 font-mono">
                    {dirPath}/
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main View: Code Viewer */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#090d18]">
        {/* Code Header Bar */}
        <div className="h-12 border-b border-white/5 px-4 flex items-center justify-between bg-[#0e1424] flex-shrink-0">
          <div className="flex items-center space-x-2 truncate">
            <FileCode className="w-4 h-4 text-cyan-400 flex-shrink-0" />
            <span className="text-xs font-mono text-cyan-200 truncate font-semibold">
              {currentFile}
            </span>
            {lineCount > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                {lineCount} lines
              </span>
            )}
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-slate-200 transition-all active:scale-95"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 text-xs">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-400" />
                <span>Copy Code</span>
              </>
            )}
          </button>
        </div>

        {/* Code Viewer Body */}
        <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-slate-300 selection:bg-cyan-500/20 selection:text-cyan-200">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-slate-500 space-x-2">
              <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
              <span>Loading code...</span>
            </div>
          ) : (
            <pre className="whitespace-pre">
              <code>{fileContent}</code>
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};
