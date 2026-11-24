import { apiUrl } from '../../config';

export default function EmptyCourses() {
  return (
    <div className="glass-panel p-8 text-center">
      <div className="text-3xl mb-3">◆</div>
      <h3 className="text-white text-lg mb-2">Нет курсов</h3>
      <p className="text-gray-400 text-sm">Подключите аккаунт Stepik для импорта курсов</p>
      <a
        href={apiUrl('/auth/login')}
        className="inline-block mt-4 px-6 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium"
      >
        Подключить Stepik
      </a>
    </div>
  );
}
